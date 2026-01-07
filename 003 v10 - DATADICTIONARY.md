# DATADICTIONARY (ETF_ITA)

**Package:** v10.8 (naming canonico)  
**Doc Revision:** r42 — 2026-01-07  
**Stato:** PRODUCTION READY v10.8  

**Database:** `data/db/etf_data.duckdb` (DuckDB embedded)  
**DB Backups:** `data/db/backups/etf_data_backup_<timestamp>.duckdb`  

**Production:**  
- Orders (commit): `data/production/orders/orders_<timestamp>.json`  
- Forecasts (dry-run): `data/production/forecasts/forecast_<timestamp>.json`  
- Postcasts: `data/production/postcasts/postcast_<timestamp>.json`  
- KPI Forecast: `data/production/forecasts/kpi_forecast_<timestamp>.json` (metriche ordini proposti)  
- KPI Postcast: `data/production/postcasts/kpi_postcast_<timestamp>.json` (metriche post-execution)

**Backtests:**  
- Run directory: `data/backtests/runs/backtest_<preset>_<timestamp>/`  
- KPI: `data/backtests/runs/backtest_<preset>_<timestamp>/kpi.json` (metriche performance)  
- Orders: `data/backtests/runs/backtest_<preset>_<timestamp>/orders.json` (ordini eseguiti)  
- Portfolio: `data/backtests/runs/backtest_<preset>_<timestamp>/portfolio.json` (evoluzione posizioni)  
- Trades: `data/backtests/runs/backtest_<preset>_<timestamp>/trades.json` (summary trade)  
- Summary: `data/backtests/reports/backtest_summary_<batch_ts>.json` (aggregato multi-preset)

**Reports:** `data/reports/sessions/<timestamp>/[01_health_checks|02_data_quality|03_guardrails|04_risk_management|05_stress_tests|06_strategy_analysis|07_backtest_validation|08_performance_summary]/`  

**Config:**  
- ETF Universe: `config/etf_universe.json`  
- Market Calendar: `config/market_holidays.json` (festività + exceptional_closures)

**Scripts:** (riorganizzati per chiarezza)
- `scripts/setup/`: Setup & initialization (setup_db, load_trading_calendar)
- `scripts/data/`: Data pipeline (ingest_data, compute_signals, extend_historical_data)
- `scripts/trading/`: Strategy & execution (strategy_engine, execute_orders, update_ledger)
- `scripts/backtest/`: Backtesting (backtest_engine, backtest_runner)
- `scripts/quality/`: Data quality & health (health_check, sanity_check, spike_detector, zombie_exclusion_enforcer, data_quality_audit)
- `scripts/risk/`: Risk management (check_guardrails, implement_risk_controls, enhanced_risk_management, diversification_guardrails, vol_targeting, trailing_stop_v2)
- `scripts/fiscal/`: Tax & fiscal (tax_engine)
- `scripts/reports/`: Reports & analysis (performance_report_generator, stress_test, production_kpi)
- `scripts/orchestration/`: Workflow orchestration (sequence_runner, session_manager, automated_test_cycle)
- `scripts/utils/`: Shared utilities (path_manager, market_calendar, console_utils)
- `scripts/maintenance/`: Maintenance scripts (update_market_calendar)

**Docs:** (riorganizzati)
- `docs/backups/`: Backup ZIP files
- `docs/schema/v003/`: DB schema contract (versioned)
- `docs/history/fixes/`: Bug fix reports
- `docs/history/features/`: Feature implementation reports
- `docs/history/tests/`: Test analysis reports

**Temp:** `temp/` (script temporanei, auto-cleanup)

**System Status:** CANDIDATE PRODUCTION  
**Baseline produzione:** EUR / ACC (FX e DIST disattivati salvo feature flag)

---

## DD-0. Principi
- Tipi numerici di mercato: `DOUBLE` (performance).  
- Valori contabili: arrotondare a 2 decimali in query/report (no cast pervasivi).  
- Date: `DATE` nativo.  
- Tabelle principali: `created_at` e `last_updated`.
- Convenzione prezzi: `adj_close` per segnali, `close` per valorizzazione ledger (DIPF §2.1).
- Baseline EUR/ACC: `currency='EUR'` e `dist_policy='ACC'` per strumenti attivi; non-EUR/DIST richiedono feature flag.

## DD-0.1 Database Objects (tabelle e viste)

Questa sezione elenca gli oggetti database principali.

**Tabelle principali:**

- `market_data` - Dati storici prezzi (OHLCV)
- `corporate_actions` - Eventi corporate actions
- `trading_calendar` - Calendario trading borse
- `symbol_registry` - Registry simboli e metadati
- `fx_rates` - Tassi di cambio FX
- `ingestion_audit` - Audit ingestione dati
- `staging_data` - Area staging per validazione
- `signals` - Segnali strategia
- `fiscal_ledger` - Ledger fiscale PMC
- `tax_loss_carryforward` - Zainetto minusvalenze per categoria fiscale
- `trade_journal` - Journal operazioni
- `metric_snapshot` - Snapshot metriche
- `benchmark_snapshot` - Snapshot benchmark
- `run_registry` - Registry esecuzioni

**Viste principali:**

- `portfolio_overview` - Vista portafoglio
- `trade_actions_log` - Log azioni trading
- `benchmark_after_tax_eur` - Benchmark after-tax EUR
- `risk_metrics` - Metriche di rischio (volatility, drawdown, SMA) con close/volume per strategy_engine

---

## DD-0.2 Filesystem Artifacts (Run Package)

Questa sezione elenca gli artifact generati dal sistema.

**Run Package Files:**

- `manifest.json` - Metadata esecuzione
- `kpi.json` - KPI performance
- `summary.md` - Report riassuntivo
- `orders.json` - Ordini proposti

**Report Files:**

- `health_report.md` - Health check report
- `stress_test.json` - Stress test results
- `automated_test_cycle.json` - Test cycle results

Nota: DuckDB non fa affidamento su indici tradizionali per performance come RDBMS OLTP; la strategia di performance è basata su schema "lean", bulk insert, funzioni finestra e snapshot/materializzazioni quando necessario.

---

## DD-1. Storage fisico
- File DB: `data/etf_data.duckdb`
- Snapshot/export: Parquet (opzionale)
- Run Package operativo: filesystem **session-based** `data/reports/sessions/<timestamp>/...` (vedi DD-0.2)
- `data/reports/<run_id>/` rimane **export opzionale** (non obbligatorio nel baseline)

---

## DD-2. Tabelle dati di mercato

### DD-2.1 `market_data`
Serie storica prezzi EOD.

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | PK (composita) |
| date | DATE | PK (composita) |
| close | DOUBLE | prezzo raw (ledger valuation) |
| adj_close | DOUBLE | prezzo adjusted (signals/returns) |
| volume | BIGINT | >= 0 |
| currency | VARCHAR | es. EUR (baseline) |
| provider | VARCHAR | es. YF, TIINGO |
| created_at | TIMESTAMP | default now() |
| last_updated | TIMESTAMP | default now() |

**PK:** (`symbol`, `date`)

### DD-2.2 `corporate_actions` (opzionale, warning-only)
Tabella minima per split/dividendi (solo per cross-check).

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | |
| date | DATE | |
| type | VARCHAR | 'DIVIDEND' / 'SPLIT' |
| amount | DOUBLE | €/share o ratio |
| created_at | TIMESTAMP | |

**PK:** (`symbol`, `date`, `type`)

---

## DD-3. Trading calendar e registry strumenti

### DD-3.1 `trading_calendar`
| Colonna | Tipo | Note |
|---|---|---|
| venue | VARCHAR | es. BIT, XETRA |
| date | DATE | |
| is_open | BOOLEAN | |
| created_at | TIMESTAMP | |

**PK:** (`venue`, `date`)

### DD-3.2 `symbol_registry`
Anagrafica strumenti e gestione ticker-change/survivorship (lean).

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | PK |
| name | VARCHAR | descrizione |
| venue | VARCHAR | BIT/XETRA |
| currency | VARCHAR | EUR (baseline) |
| dist_policy | VARCHAR | ACC (baseline) |
| max_daily_move_pct | DOUBLE | soglia spike (es. 0.15 = 15%), opzionale |
| tax_category | VARCHAR | `OICR_ETF` default |
| parent_symbol | VARCHAR | alias/mapping (opz.) |
| status | VARCHAR | ACTIVE/STALLED/DELISTED |
| created_at | TIMESTAMP | |
| last_updated | TIMESTAMP | |

---

## DD-4. FX (feature flag)

### DD-4.1 `fx_rates`
Usata solo se `currency != EUR` è consentito (non nel baseline).

| Colonna | Tipo | Note |
|---|---|---|
| pair | VARCHAR | es. USDEUR |
| date | DATE | |
| rate | DOUBLE | quote base in quote |
| source | VARCHAR | provider |
| created_at | TIMESTAMP | |

**PK:** (`pair`, `date`)

---

## DD-5. Audit ingestione

### DD-5.1 `ingestion_audit`
| Colonna | Tipo | Note |
|---|---|---|
| audit_id | BIGINT | PK |
| run_id | VARCHAR | opz. |
| provider | VARCHAR | |
| venue | VARCHAR | |
| date_min | DATE | |
| date_max | DATE | |
| rows_fetched | BIGINT | |
| rows_accepted | BIGINT | |
| rows_rejected | BIGINT | |
| reject_summary | VARCHAR | sintetico |
| provider_schema_hash | VARCHAR | compatibilità fallback |
| created_at | TIMESTAMP | |

### DD-5.2 `staging_data`
Tabella di transito per validazione dati.

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | PK (composita) |
| date | DATE | PK (composita) |
| high | DOUBLE | |
| low | DOUBLE | |
| close | DOUBLE | |
| adj_close | DOUBLE | |
| volume | BIGINT | >= 0 |
| source | VARCHAR | provider |
| created_at | TIMESTAMP | |

**PK:** (`symbol`, `date`)

---

## DD-6. Signal Engine

### DD-6.1 `signals`
Tabella segnali oggettivi generati dal Signal Engine.

| Colonna | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| date | DATE | data segnale |
| symbol | VARCHAR | strumento |
| signal_state | VARCHAR | RISK_ON/RISK_OFF/HOLD |
| risk_scalar | DOUBLE | 0..1 sizing |
| explain_code | VARCHAR | spiegazione |
| sma_200 | DOUBLE | media mobile 200gg |
| volatility_20d | DOUBLE | volatilità 20gg |
| spy_guard | BOOLEAN | guardia S&P 500 |
| regime_filter | VARCHAR | regime volatilità |
| created_at | TIMESTAMP | |

**PK:** (`id`)
**Index:** (`date`, `symbol`), (`signal_state`)

---

## DD-7. Fiscalità e ledger

### DD-7.1 `fiscal_ledger`
Registro operazioni e stato contabile.

| Colonna | Tipo | Note |
|---|---|---|
| id | BIGINT | PK |
| run_id | VARCHAR | link run |
| date | DATE | data operazione (EOD model) |
| type | VARCHAR | BUY/SELL/INTEREST/(DIVIDEND opz.) |
| symbol | VARCHAR | |
| qty | DOUBLE | quote |
| price | DOUBLE | prezzo unitario (valuta strumento) |
| price_eur | DOUBLE | controvalore EUR (se FX) |
| exchange_rate_used | DOUBLE | null nel baseline |
| cash_delta_eur | DOUBLE | variazione cash in EUR |
| pmc_eur | DOUBLE | PMC in EUR |
| realized_pnl_eur | DOUBLE | su SELL |
| tax_paid_eur | DOUBLE | imposta pagata |
| tax_category_snapshot | VARCHAR | copia da registry |
| created_at | TIMESTAMP | |
| last_updated | TIMESTAMP | |

**Note importanti:**
- `INTEREST`: Evento mensile su cash_balance con tasso da config
- `pmc_eur`: Calcolato come prezzo medio ponderato continuo
- Arrotondamenti a 2 decimali in query fiscali

### DD-7.2 `tax_loss_carryforward`
Minusvalenze "redditi diversi" riportabili per categoria fiscale (DIPF §6.2).

| Colonna | Tipo | Note |
|---|---|---|
| id | INTEGER | PK auto-increment |
| symbol | VARCHAR | Simbolo origine loss (audit trail) |
| realize_date | DATE | Data realizzo loss |
| loss_amount | DOUBLE | Importo loss (negativo) |
| used_amount | DOUBLE | Importo già utilizzato (>= 0) |
| expires_at | DATE | Scadenza 31/12/(anno+4) |
| tax_category | VARCHAR | Categoria fiscale (OICR_ETF/ETC_ETN_STOCK) |
| created_at | TIMESTAMP | default now() |

**Note implementazione:**
- Query zainetto per `tax_category`, non per simbolo
- OICR_ETF: gain tassati pieni 26%, loss accumulate ma non compensabili
- ETC_ETN_STOCK: compensazione possibile per categoria
- Scadenza conforme normativa italiana: 31/12 quarto anno successivo

### DD-7.3 `trade_journal`

| Colonna | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| run_id | VARCHAR | esecuzione univoca |
| symbol | VARCHAR | strumento |
| signal_state | VARCHAR | RISK_ON/OFF/HOLD |
| risk_scalar | DOUBLE | 0..1 sizing |
| explain_code | VARCHAR | spiegazione segnale |
| flag_override | BOOLEAN | default FALSE |
| override_reason | VARCHAR | se override manuale |
| theoretical_price | DOUBLE | prezzo atteso |
| realized_price | DOUBLE | prezzo eseguito |
| slippage_bps | DOUBLE | slippage in basis points |
| created_at | TIMESTAMP | |

**Utilità:**
- Audit trail completo da segnale a esecuzione
- Tracking performance vs segnali
- Debug discrepanze
- Compliance reporting

**PK:** (`id`)
**Index:** (`run_id`, `symbol`)

---

## DD-8. Metriche e snapshot

### DD-8.1 `metric_snapshot`
Snapshot KPI portfolio-level (post-run).

| Colonna | Tipo | Note |
|---|---|---|
| run_id | VARCHAR | PK |
| as_of_date | DATE | |
| cagr | DOUBLE | |
| max_dd | DOUBLE | |
| vol | DOUBLE | |
| sharpe | DOUBLE | |
| turnover | DOUBLE | |
| kpi_hash | VARCHAR | hash KPI canonici |
| created_at | TIMESTAMP | |

### DD-8.2 `benchmark_snapshot`
| Colonna | Tipo | Note |
|---|---|---|
| run_id | VARCHAR | PK |
| benchmark_symbol | VARCHAR | |
| cagr | DOUBLE | |
| max_dd | DOUBLE | |
| vol | DOUBLE | |
| sharpe | DOUBLE | |
| kpi_hash | VARCHAR | |
| created_at | TIMESTAMP | |

Nota: il calcolo "after-tax" del benchmark dipende da `benchmark_kind` (vedi DD-10.3 e DIPF §7.2.1).

---

## DD-9. Run Registry (opzionale ma raccomandato)

### DD-9.1 `run_registry`
Indice delle run (non sostituisce i file).

| Colonna | Tipo | Note |
|---|---|---|
| run_id | VARCHAR | PK |
| run_ts | TIMESTAMP | |
| mode | VARCHAR | BACKTEST/LIVE_SIM/DRY_RUN |
| config_hash | VARCHAR | |
| data_fingerprint | VARCHAR | rowcount+maxdate per symbol |
| kpi_hash | VARCHAR | |
| status | VARCHAR | OK/FAILED |
| report_path | VARCHAR | `data/reports/sessions/<timestamp>/...` (operativo) oppure `data/reports/<run_id>/` (export opzionale) |
| created_at | TIMESTAMP | |

---

## DD-10. Views (output ergonomico)

### DD-10.1 `portfolio_overview`
Vista: qty, pmc, market_value, unrealized_pnl, ecc.

### DD-10.2 `trade_actions_log`
Join `fiscal_ledger` + `trade_journal` per log motivazioni/azioni.

### DD-10.3 `benchmark_after_tax_eur`
Vista comparabile "apples-to-apples" (EUR, proxy costi/tasse).
- Se `benchmark_kind=INDEX`: **no** tassazione simulata (solo friction proxy: TER/slippage/fees).
- Se `benchmark_kind=ETF`: tassazione simulata coerente con `tax_category`.

---

## DD-11. Run Package (filesystem artifacts)

### DD-11.1 `manifest.json` (minimo)
Campi obbligatori:
- `run_id`, `run_ts`, `mode`
- `execution_model`, `cost_model`, `tax_model`
- `currency_base` (EUR)
- `universe` (lista strumenti + tax_category + dist_policy)
- `benchmark_symbol`, `benchmark_kind` (`ETF`/`INDEX`)
- `config_hash`, `data_fingerprint`

### DD-11.2 `kpi.json` (minimo)
- KPI portfolio (cagr, max_dd, vol, sharpe, turnover)
- componenti costo/tasse (fees, taxes, slippage_est)
- `kpi_hash`

### DD-11.3 `summary.md`
Una pagina leggibile con:
- parametri principali
- KPI + confronto benchmark (se presente)
- sezione "Emotional Gap" (se journaling disponibile)

### DD-11.4 `orders.json` (dry-run)
Output diff-friendly di EP-07.
Campi minimi consigliati:
- elenco ordini (BUY/SELL/HOLD) con qty, symbol, reason, `explain_code`
- stime: `momentum_score`, `fees_est`, `tax_friction_est`
- `trade_score` e `recommendation` (`HOLD`/`TRADE`)

**Strutture dati corrette:**
```json
{
  "orders": [
    {
      "symbol": "XS2L.MI",
      "action": "BUY",
      "qty": 50,
      "price": 12.30,
      "reason": "RISK_ON_MOMENTUM_0.8",
      "momentum_score": 0.8,
      "fees_est": 5.20,
      "tax_friction_est": 0.00,
      "trade_score": 0.65,
      "recommendation": "TRADE"
    }
  ]
}
```

**positions_dict structure (corretta):**
```python
positions_dict = {
    'XS2L.MI': {
        'qty': 50,
        'avg_buy_price': 12.30  # NON 'avg_price'
    }
}
```

**apply_position_caps output:**
```python
capped_weights = {
    'IEAC.MI': 0.325,  # Ridistribuito proporzionalmente
    'XS2L.MI': 0.350,  # Cap rispettato (max 0.35)
    'EIMI.MI': 0.325   # Peso eccedente ridistribuito
}
# Somma = 1.0, cap garantiti
```

**momentum_score modellistico:**
```python
# Base score 0-1
base_momentum = 0.5

# Adjust per risk scalar e volatilità
momentum_score = base_momentum * risk_scalar * vol_adjustment
# Clamp 0-1
momentum_score = max(0, min(1, momentum_score))
```

---

## DD-12. Schema Contract

**File:** `docs/schema/SCHEMA_CONTRACT.json`  
**Gate:** `tests/test_schema_validation.py`  
**Validazione:** `tests/test_schema_validation.py`

Single source of truth per schema database e naming conventions. Impedisce drift sistemici.

### Tabelle con contract vincolante:
- `market_data` - Dati OHLCV con convenzione adj_close/close
- `fiscal_ledger` - Ledger PMC con colonne fiscali complete  
- `signals` - Segnali strategia con risk scalar
- `tax_loss_carryforward` - Zainetto per categoria fiscale

### Viste critiche garantite:
- `risk_metrics` - Con close/volume per strategy_engine
- `portfolio_summary` - Con valori market coerenti
- `execution_prices` - Prezzi esecuzione realistici

### Gate operativo:
- Blocca esecuzione se schema non conforme
- Verifica colonne critiche per viste
- Validazione syntax script core
- Cleanup automatico ambiente test

---

## Cross-Reference
- Design framework: vedi DIPF  
- Piano implementazione: vedi TODOLIST  
- Comandi operativi: vedi README  
- Regole operative: vedi AGENT_RULES
