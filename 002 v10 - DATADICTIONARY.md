# DATADICTIONARY (ETF_ITA)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r34 — 2026-01-06  
**Database:** DuckDB embedded (`data/etf_data.duckdb`)  
**Reports Structure:** `data/reports/sessions/<timestamp>/[01_health_checks|02_automated|03_guardrails|04_risk|05_stress_tests|06_strategy|07_backtests|08_performance|09_analysis]/`  
**Risk Analysis:** `data/reports/sessions/<timestamp>/04_risk/risk_management_*.json`  
**Risk Summary:** `data/reports/sessions/<timestamp>/08_performance/performance_*.json`  
**System Status:** **PRODUCTION READY v10.7.2**  
| **Strategy Engine:** **CRITICAL FIXES COMPLETATI** (bug risolti) |
| **Fiscal Engine:** **CRITICAL FIXES COMPLETATI** (zainetto per categoria, integrazione completa) |
| **Guardrails:** **CRITICAL BUGS RISOLTI** (NameError + price coherence) | 
**Scripts Funzionanti:** **13/13** (100% success)  
**Closed Loop:** **IMPLEMENTATO** (execute_orders.py + run_complete_cycle.py)  
**Baseline produzione:** **EUR / ACC** (FX e DIST disattivati salvo feature flag)  

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

Nota: DuckDB non fa affidamento su indici tradizionali per performance come RDBMS OLTP; la strategia di performance è basata su schema “lean”, bulk insert, funzioni finestra e snapshot/materializzazioni quando necessario.

---

## DD-1. Storage fisico
- File DB: `data/etf_data.duckdb`
- Snapshot/export: Parquet (opzionale) + Run Package su filesystem (`data/reports/<run_id>/`)

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

### DD-6.1 `fiscal_ledger`
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

### DD-9.1 `metric_snapshot`
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

### DD-9.2 `benchmark_snapshot`
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


Nota: il calcolo “after-tax” del benchmark dipende da `benchmark_kind` (vedi DD-10.3 e DIPF §7.2.1).

---


## DD-10. Run Registry (opzionale ma raccomandato)

### DD-10.1 `run_registry`
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
| report_path | VARCHAR | `data/reports/<run_id>` |
| created_at | TIMESTAMP | |

---

## DD-11. Views (output ergonomico)

### DD-11.1 `portfolio_overview`
Vista: qty, pmc, market_value, unrealized_pnl, ecc.

### DD-11.2 `trade_actions_log`
Join `fiscal_ledger` + `trade_journal` per log motivazioni/azioni.

### DD-11.3 `benchmark_after_tax_eur`
Vista comparabile “apples-to-apples” (EUR, proxy costi/tasse).
- Se `benchmark_kind=INDEX`: **no** tassazione simulata (solo friction proxy: TER/slippage/fees).
- Se `benchmark_kind=ETF`: tassazione simulata coerente con `tax_category`.

---

## DD-12. Run Package (filesystem artifacts)

### DD-12.1 `manifest.json` (minimo)
Campi obbligatori:
- `run_id`, `run_ts`, `mode`
- `execution_model`, `cost_model`, `tax_model`
- `currency_base` (EUR)
- `universe` (lista strumenti + tax_category + dist_policy)
- `benchmark_symbol`, `benchmark_kind` (`ETF`/`INDEX`)
- `config_hash`, `data_fingerprint`

### DD-12.2 `kpi.json` (minimo)
- KPI portfolio (cagr, max_dd, vol, sharpe, turnover)
- componenti costo/tasse (fees, taxes, slippage_est)
- `kpi_hash`

### DD-12.3 `summary.md`
Una pagina leggibile con:
- parametri principali
- KPI + confronto benchmark (se presente)
- sezione "Emotional Gap" (se journaling disponibile)


### DD-12.4 `orders.json` (dry-run)
Output diff-friendly di EP-07.
Campi minimi consigliati:
- elenco ordini (BUY/SELL/HOLD) con qty, symbol, reason, `explain_code`
- stime: `expected_alpha_est`, `fees_est`, `tax_friction_est`
- `do_nothing_score` e `recommendation` (`HOLD`/`TRADE`)

**🆕 Strutture dati corrette (v10.7.1):**
```json
{
  "orders": [
    {
      "symbol": "XS2L.MI",
      "action": "BUY",
      "qty": 50,
      "price": 12.30,
      "reason": "RISK_ON_MOMENTUM_0.8",
      "expected_alpha_est": 1.66,
      "fees_est": 5.20,
      "tax_friction_est": 0.00,
      "do_nothing_score": 0.0012,
      "recommendation": "TRADE"
    }
  ]
}
```

**🆕 positions_dict structure (corretta):**
```python
positions_dict = {
    'XS2L.MI': {
        'qty': 50,
        'avg_buy_price': 12.30  # NON 'avg_price'
    }
}
```

**🆕 apply_position_caps output:**
```python
capped_weights = {
    'IEAC.MI': 0.325,  # Ridistribuito proporzionalmente
    'XS2L.MI': 0.350,  # Cap rispettato (max 0.35)
    'EIMI.MI': 0.325   # Peso eccedente ridistribuito
}
# Somma = 1.0, cap garantiti
```

**🆕 expected_alpha modellistico:**
```python
# Base: 8% annual
base_alpha = 0.08
# Adjust per risk scalar e volatilità
risk_adjusted_alpha = base_alpha * risk_scalar * vol_adjustment
# Converti in daily
daily_alpha = (1 + risk_adjusted_alpha) ** (1/252) - 1
expected_alpha = position_value * daily_alpha
```
