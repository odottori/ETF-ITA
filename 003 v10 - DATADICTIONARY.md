# DATADICTIONARY (ETF_ITA)

**Package:** v10.8.4 (naming canonico)  
**Doc Revision:** r48 — 2026-01-08  
**Stato**: BACKTEST-READY v10.8.4 + DECISION SUPPORT + MONTE CARLO GATE + CALENDAR HEALING — SCHEMA FIX COMPLETATI  

**Database:** `data/db/etf_data.duckdb` (DuckDB embedded)  
**DB Backups:** `data/db/backups/etf_data_backup_<timestamp>.duckdb`  

**Production:**  
- Orders: `data/production/orders/orders_<timestamp>.json` (ordini reali commit)
- Forecasts KPI: `data/production/forecasts/kpi_forecast_<timestamp>.json` (KPI ordini proposti dry-run)
- Postcasts KPI: `data/production/postcasts/kpi_postcast_<timestamp>.json` (KPI post-esecuzione)

**Backtests:**  
- Run directory: `data/backtests/runs/backtest_<preset>_<timestamp>/`  
- KPI: `data/backtests/runs/backtest_<preset>_<timestamp>/kpi.json`  
- Orders: `data/backtests/runs/backtest_<preset>_<timestamp>/orders.json`  
- Portfolio: `data/backtests/runs/backtest_<preset>_<timestamp>/portfolio.json`  
- Trades: `data/backtests/runs/backtest_<preset>_<timestamp>/trades.json`  
- Summary: `data/backtests/reports/backtest_summary_<batch_ts>.json`

**Reports:** `data/reports/sessions/<timestamp>/[01_health_checks|02_data_quality|03_guardrails|04_risk_management|05_stress_tests|06_strategy_analysis|07_backtest_validation|08_performance_summary]/`  
**Portfolio Risk Monitor:** `data/reports/sessions/<timestamp>/05_stress_tests/portfolio_risk_<timestamp>.json` (VaR/CVaR monitoring posizioni correnti)  
**Monte Carlo Stress Test:** `data/reports/sessions/<timestamp>/05_stress_tests/monte_carlo_stress_test_<timestamp>.[json|md]` (gate finale pre-AUM, DIPF §9.3)  

**Config:**  
- ETF Universe: `config/etf_universe.json`  
- Market Calendar: `config/market_holidays.json`  
- Reports Config: `config/reports_config.json`

**Scripts:** (organizzazione reale)
- `scripts/setup/`: Setup & initialization (setup_db, load_trading_calendar, migrate_*)
- `scripts/data/`: Data pipeline (ingest_data, compute_signals, extend_historical_data)
- `scripts/trading/`: Strategy & execution (strategy_engine, strategy_engine_v2, execute_orders, update_ledger)
- `scripts/backtest/`: Backtesting (backtest_engine, backtest_runner)
- `scripts/quality/`: Data quality & health (health_check, sanity_check, spike_detector, zombie_exclusion_enforcer, data_quality_audit, schema_contract_gate)
- `scripts/risk/`: Risk management (check_guardrails, implement_risk_controls, enhanced_risk_management, diversification_guardrails, vol_targeting, trailing_stop_v2)
- `scripts/fiscal/`: Tax & fiscal (tax_engine)
- `scripts/reports/`: Reports & analysis (performance_report_generator, stress_test, production_kpi)
- `scripts/orchestration/`: Workflow orchestration (sequence_runner, session_manager, automated_test_cycle)
- `scripts/utils/`: Shared utilities (path_manager, market_calendar, console_utils, universe_helper)
- `scripts/maintenance/`: Maintenance scripts (update_market_calendar, backup_db, restore_db)
- `scripts/analysis/`: Analysis tools (stress_test_monte_carlo, run_stress_test_example, analyze_forecast_accuracy, diagnose_execution_rate, regime_adaptive_poc_*)
- `scripts/strategy/`: Strategy modules (portfolio_construction)
- `scripts/temp/`: Temporary scripts (auto-cleanup)
- `scripts/archive/`: Historical scripts (non-production)

**Docs:**
- `docs/backups/`: Backup ZIP files
- `docs/schema/v003/`: DB schema contract (versioned)
- `docs/history/fixes/`: Bug fix reports
- `docs/history/features/`: Feature implementation reports
- `docs/history/tests/`: Test analysis reports
- `docs/history/performance/`: Performance reports

**Temp:** `temp/` (script temporanei, auto-cleanup)

**Baseline produzione:** EUR / ACC (FX e DIST disattivati salvo feature flag)

---

## DD-0. Principi

- Tipi numerici di mercato: `DOUBLE` (performance)
- Valori contabili: arrotondare a 2 decimali in query/report (no cast pervasivi)
- Date: `DATE` nativo
- Tabelle principali: `created_at` e opzionalmente `updated_at`
- Convenzione prezzi: `adj_close` per segnali, `close` per valorizzazione ledger (DIPF §2.1)
- Baseline EUR/ACC: `currency='EUR'` e `distribution_policy='ACC'` per strumenti attivi

---

## DD-0.1 Database Objects (19 tabelle + 4 viste)

**Tabelle principali (19):**

1. `market_data` - Dati storici prezzi (OHLCV)
2. `staging_data` - Area staging per validazione
3. `trading_calendar` - Calendario trading borse
4. `symbol_registry` - Registry simboli e metadati
5. `ingestion_audit` - Audit ingestione dati
6. `signals` - Segnali strategia
7. `fiscal_ledger` - Ledger fiscale PMC (26 colonne)
8. `tax_loss_carryforward` - Zainetto minusvalenze per categoria fiscale
9. `trade_journal` - Journal operazioni
10. `orders` - Ordini generati
11. `orders_plan` - Piano ordini con decision path
12. `position_plans` - Piani posizioni con holding period
13. `position_events` - Eventi posizioni (extend/close)
14. `position_peaks` - Peak tracking per trailing stop
15. `daily_portfolio` - Portfolio giornaliero (tabella backtest)
16. `portfolio_overview` - Vista portfolio (VISTA)
17. `portfolio_summary` - Summary portfolio corrente (VISTA)
18. `execution_prices` - Prezzi esecuzione (VISTA)
19. `risk_metrics` - Metriche di rischio (VISTA)

**Viste (4):**
- `portfolio_overview` - Vista portafoglio time-series
- `portfolio_summary` - Vista summary posizioni correnti
- `execution_prices` - Vista prezzi esecuzione (close + volume)
- `risk_metrics` - Vista metriche rischio (volatility, drawdown, SMA, close, volume)

---

## DD-1. Tabelle Dati di Mercato

### DD-1.1 `market_data`
Serie storica prezzi EOD.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| symbol | VARCHAR | NO | - | PK (composita) |
| date | DATE | NO | - | PK (composita) |
| adj_close | DOUBLE | YES | - | prezzo adjusted (signals/returns) |
| close | DOUBLE | YES | - | prezzo raw (ledger valuation) |
| high | DOUBLE | YES | - | massimo giornaliero |
| low | DOUBLE | YES | - | minimo giornaliero |
| volume | BIGINT | YES | - | volume scambiato |
| source | VARCHAR | YES | 'YF' | provider dati |

**PK:** (`symbol`, `date`)

---

### DD-1.2 `staging_data`
Tabella di transito per validazione dati prima di merge in market_data.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| symbol | VARCHAR | NO | - | PK (composita) |
| date | DATE | NO | - | PK (composita) |
| adj_close | DOUBLE | YES | - | prezzo adjusted |
| close | DOUBLE | YES | - | prezzo raw |
| high | DOUBLE | YES | - | massimo |
| low | DOUBLE | YES | - | minimo |
| volume | BIGINT | YES | - | volume |
| source | VARCHAR | YES | 'YF' | provider |

**PK:** (`symbol`, `date`)

---

## DD-2. Trading Calendar e Registry

### DD-2.1 `trading_calendar`

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| venue | VARCHAR | NO | - | PK (es. BIT) |
| date | DATE | NO | - | PK |
| is_open | BOOLEAN | NO | true | mercato aperto (base) |
| quality_flag | VARCHAR | YES | NULL | calendar healing: zombie_price/large_gap/spike/manual_exclusion |
| flagged_at | TIMESTAMP | YES | - | quando flaggato |
| flagged_reason | TEXT | YES | - | descrizione issue |
| retry_count | INTEGER | YES | 0 | tentativi healing |
| last_retry | TIMESTAMP | YES | - | ultimo tentativo |
| healed_at | TIMESTAMP | YES | - | quando healed |

**PK:** (`venue`, `date`)  
**Indici:** `idx_trading_calendar_quality_flag`, `idx_trading_calendar_retry_pending`  
**Note:** Calendar Healing System (v10.8.4) - gestione auto-correttiva data quality  
**Schema Fix v10.8.4:** Colonne healing integrate in setup_db.py (prima richiedevano migrazione manuale)

---

### DD-2.2 `symbol_registry`
Anagrafica strumenti con metadati fiscali e status.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| symbol | VARCHAR | NO | - | PK |
| name | VARCHAR | NO | - | descrizione |
| is_active | BOOLEAN | YES | true | attivo |
| status | VARCHAR | YES | 'ACTIVE' | ACTIVE/STALLED/DELISTED |
| category | VARCHAR | NO | - | ETF/ETC/STOCK |
| currency | VARCHAR | NO | - | EUR (baseline) |
| distribution_policy | VARCHAR | YES | 'ACC' | ACC/DIST |
| tax_category | VARCHAR | YES | 'OICR_ETF' | OICR_ETF/ETC_ETN_STOCK |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |
| updated_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`symbol`)

---

## DD-3. Audit Ingestione

### DD-3.1 `ingestion_audit`

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| run_id | VARCHAR | NO | - | identificativo run |
| provider | VARCHAR | NO | 'YF' | provider dati |
| symbol | VARCHAR | YES | - | simbolo ingerito |
| start_date | DATE | YES | - | data inizio |
| end_date | DATE | YES | - | data fine |
| records_accepted | INTEGER | YES | 0 | record accettati |
| records_rejected | INTEGER | YES | 0 | record rifiutati |
| rejection_reasons | VARCHAR | YES | - | motivi rifiuto |
| provider_schema_hash | VARCHAR | YES | - | hash schema provider |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`id`)

---

## DD-4. Signal Engine

### DD-4.1 `signals`
Tabella segnali oggettivi generati dal Signal Engine.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| date | DATE | NO | - | UNIQUE (date, symbol) |
| symbol | VARCHAR | NO | - | UNIQUE (date, symbol) |
| signal_state | VARCHAR | NO | - | RISK_ON/RISK_OFF/HOLD |
| risk_scalar | DOUBLE | YES | - | 0..1 sizing |
| explain_code | VARCHAR | YES | - | spiegazione segnale |
| sma_200 | DOUBLE | YES | - | media mobile 200gg |
| volatility_20d | DOUBLE | YES | - | volatilità 20gg |
| spy_guard | BOOLEAN | YES | false | guardia S&P 500 |
| regime_filter | VARCHAR | YES | 'NEUTRAL' | regime volatilità |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`id`)  
**UNIQUE:** (`date`, `symbol`)

---

## DD-5. Fiscalità e Ledger

### DD-5.1 `fiscal_ledger` (26 colonne)
Registro operazioni e stato contabile con holding period tracking.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| date | DATE | NO | - | data operazione (EOD model) |
| type | VARCHAR | NO | - | BUY/SELL/DEPOSIT/INTEREST |
| symbol | VARCHAR | NO | - | strumento |
| qty | DOUBLE | NO | - | quantità |
| price | DOUBLE | NO | - | prezzo unitario |
| fees | DOUBLE | YES | 0.0 | commissioni + slippage |
| tax_paid | DOUBLE | YES | 0.0 | imposta pagata |
| pmc_snapshot | DOUBLE | YES | - | PMC snapshot |
| trade_currency | VARCHAR | YES | 'EUR' | valuta trade |
| exchange_rate_used | DOUBLE | YES | 1.0 | tasso cambio |
| price_eur | DOUBLE | YES | - | controvalore EUR |
| run_id | VARCHAR | YES | - | identificativo run |
| run_type | VARCHAR | YES | 'PRODUCTION' | PRODUCTION/BACKTEST |
| notes | VARCHAR | YES | - | note libere |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |
| **entry_date** | DATE | YES | - | data entry (holding period) |
| **entry_score** | DOUBLE | YES | - | score entry |
| **expected_holding_days** | INTEGER | YES | - | giorni holding attesi |
| **expected_exit_date** | DATE | YES | - | data exit attesa |
| **actual_holding_days** | INTEGER | YES | - | giorni holding reali |
| **exit_reason** | VARCHAR | YES | - | motivo exit |
| **decision_path** | VARCHAR | YES | 'LEGACY' | percorso decisionale |
| **reason_code** | VARCHAR | YES | 'LEGACY_ORDER' | codice motivo |
| **execution_price_mode** | VARCHAR | YES | 'CLOSE_SAME_DAY_SLIPPAGE' | modalità prezzo |
| **source_order_id** | INTEGER | YES | - | ID ordine sorgente |

**PK:** (`id`)

**Cronologia Schema:**
- v10.7: Aggiunti campi holding period tracking (6 campi)
- v10.8: Aggiunti campi audit trail (`decision_path`, `reason_code`)
- v10.8: Aggiunto campo `run_type` per distinzione PRODUCTION/BACKTEST
- v10.8: Aggiunto campo `trade_currency` per supporto FX futuro

---

### DD-5.2 `tax_loss_carryforward`
Minusvalenze "redditi diversi" riportabili per categoria fiscale (DIPF §6.2).

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| symbol | VARCHAR | NO | - | simbolo origine loss |
| realize_date | DATE | NO | - | data realizzo loss |
| loss_amount | DOUBLE | NO | - | importo loss (negativo) |
| used_amount | DOUBLE | YES | 0.0 | importo già utilizzato |
| expires_at | DATE | NO | - | scadenza 31/12/(anno+4) |
| tax_category | VARCHAR | NO | - | OICR_ETF/ETC_ETN_STOCK |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`id`)

**Note implementazione:**
- Query zainetto per `tax_category`, non per simbolo
- OICR_ETF: gain tassati pieni 26%, loss accumulate ma non compensabili
- ETC_ETN_STOCK: compensazione possibile per categoria
- Scadenza conforme normativa italiana: 31/12 quarto anno successivo
- Formula zainetto disponibile: `SUM(loss_amount) + SUM(used_amount)` (somme separate per correttezza)

---

### DD-5.3 `trade_journal`
Journal operazioni per audit trail completo.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| run_id | VARCHAR | NO | - | esecuzione univoca |
| symbol | VARCHAR | NO | - | strumento |
| signal_state | VARCHAR | NO | - | RISK_ON/OFF/HOLD |
| risk_scalar | DOUBLE | YES | - | 0..1 sizing |
| explain_code | VARCHAR | YES | - | spiegazione segnale |
| flag_override | BOOLEAN | YES | false | override manuale |
| override_reason | VARCHAR | YES | - | motivo override |
| theoretical_price | DOUBLE | YES | - | prezzo atteso |
| realized_price | DOUBLE | YES | - | prezzo eseguito |
| slippage_bps | DOUBLE | YES | - | slippage in basis points |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`id`)

---

## DD-6. Orders e Planning

### DD-6.1 `orders`
Ordini generati dal sistema.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| date | DATE | NO | - | data ordine |
| symbol | VARCHAR | NO | - | strumento |
| order_type | VARCHAR | NO | - | BUY/SELL |
| qty | DOUBLE | NO | - | quantità |
| price | DOUBLE | NO | - | prezzo |
| status | VARCHAR | YES | 'PENDING' | PENDING/EXECUTED/REJECTED |
| notes | VARCHAR | YES | - | note |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`id`)

---

### DD-6.2 `orders_plan`
Piano ordini con decision path completo.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| id | INTEGER | NO | - | PK auto-increment |
| run_id | VARCHAR | NO | - | identificativo run |
| date | DATE | NO | - | data ordine |
| symbol | VARCHAR | NO | - | strumento |
| side | VARCHAR | NO | - | BUY/SELL |
| qty | DOUBLE | NO | - | quantità |
| status | VARCHAR | NO | - | PROPOSED/ACCEPTED/REJECTED |
| execution_price_mode | VARCHAR | NO | 'CLOSE_SAME_DAY_SLIPPAGE' | modalità prezzo |
| proposed_price | DOUBLE | YES | - | prezzo proposto |
| candidate_score | DOUBLE | YES | - | score candidato |
| decision_path | VARCHAR | NO | - | percorso decisionale |
| reason_code | VARCHAR | NO | - | codice motivo |
| reject_reason | VARCHAR | YES | - | motivo rifiuto |
| config_snapshot_hash | VARCHAR | YES | - | hash config |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`id`)

---

## DD-7. Position Management (Holding Period)

### DD-7.1 `position_plans`
Piani posizioni con holding period target.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| symbol | VARCHAR | NO | - | PK |
| is_open | BOOLEAN | NO | true | posizione aperta |
| entry_date | DATE | NO | - | data entry |
| entry_run_id | VARCHAR | NO | - | run ID entry |
| entry_price | DOUBLE | NO | - | prezzo entry |
| holding_days_target | INTEGER | NO | - | giorni holding target |
| expected_exit_date | DATE | NO | - | data exit attesa |
| last_review_date | DATE | YES | - | ultima review |
| current_score | DOUBLE | YES | - | score corrente |
| plan_status | VARCHAR | YES | 'ACTIVE' | ACTIVE/CLOSED/EXTENDED |
| updated_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`symbol`)

---

### DD-7.2 `position_events`
Eventi posizioni (extend/close) per audit trail.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| event_id | INTEGER | NO | - | PK auto-increment |
| run_id | VARCHAR | NO | - | identificativo run |
| date | DATE | NO | - | data evento |
| symbol | VARCHAR | NO | - | strumento |
| event_type | VARCHAR | NO | - | EXTEND/CLOSE/REVIEW |
| from_exit_date | DATE | YES | - | exit date precedente |
| to_exit_date | DATE | YES | - | exit date nuovo |
| reason_code | VARCHAR | NO | - | codice motivo |
| payload_json | VARCHAR | YES | - | payload JSON |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |

**PK:** (`event_id`)

---

### DD-7.3 `position_peaks`
Peak tracking per trailing stop.

| Colonna | Tipo | Nullable | Default | Note |
|---|---|---|---|---|
| symbol | VARCHAR | NO | - | PK (composita) |
| entry_date | DATE | NO | - | PK (composita) |
| peak_price | DECIMAL(10,4) | YES | - | prezzo peak |
| peak_date | DATE | YES | - | data peak |
| is_active | BOOLEAN | YES | true | tracking attivo |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |
| updated_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | |
| entry_price | DOUBLE | YES | - | prezzo entry |

**PK:** (`symbol`, `entry_date`)

---

## DD-8. Portfolio Views e Analytics

### DD-8.1 `daily_portfolio` (Tabella Backtest)
Portfolio giornaliero per backtest simulation.

| Colonna | Tipo | Nullable | Note |
|---|---|---|---|
| date | DATE | YES | data |
| symbol | VARCHAR | YES | strumento |
| adj_close | DOUBLE | YES | prezzo adjusted |
| volume | BIGINT | YES | volume |
| market_value | DOUBLE | YES | valore mercato |
| qty | DOUBLE | YES | quantità |
| cash | INTEGER | YES | cash disponibile |

**Utilizzo:** Creata da backtest_engine per equity curve

---

### DD-8.2 `portfolio_overview` (VISTA)
Vista time-series portfolio.

| Colonna | Tipo | Note |
|---|---|---|
| date | DATE | data |
| symbol | VARCHAR | strumento |
| adj_close | DOUBLE | prezzo adjusted |
| volume | BIGINT | volume |
| market_value | DOUBLE | valore mercato |
| qty | DOUBLE | quantità |
| cash | INTEGER | cash |

**Definizione:** Vista su daily_portfolio

---

### DD-8.3 `portfolio_summary` (VISTA)
Summary posizioni correnti.

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | strumento |
| qty | DOUBLE | quantità |
| avg_buy_price | DOUBLE | prezzo medio acquisto |
| current_price | DOUBLE | prezzo corrente (close) |
| market_value | DOUBLE | valore mercato |
| cash | DOUBLE | cash disponibile |
| total_portfolio_value | DOUBLE | valore totale portfolio |

**Definizione:** Vista aggregata fiscal_ledger + market_data

---

### DD-8.4 `execution_prices` (VISTA)
Prezzi esecuzione per strategy engine.

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | strumento |
| date | DATE | data |
| execution_price | DOUBLE | prezzo esecuzione (close) |
| volume | BIGINT | volume |
| daily_return | DOUBLE | return giornaliero |

**Definizione:** Vista su market_data (close per esecuzione)

---

### DD-8.5 `risk_metrics` (VISTA)
Metriche di rischio per signal engine.

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | strumento |
| date | DATE | data |
| adj_close | DOUBLE | prezzo adjusted (segnali) |
| close | DOUBLE | prezzo close (strategy engine) |
| volume | BIGINT | volume (strategy engine) |
| sma_200 | DOUBLE | media mobile 200gg |
| volatility_20d | DOUBLE | volatilità 20gg |
| high_water_mark | DOUBLE | massimo storico |
| drawdown_pct | DOUBLE | drawdown percentuale |
| daily_return | DOUBLE | return giornaliero |

**Definizione:** Vista calcolata su market_data con window functions

**Note:** Arricchita con `close` e `volume` in v10.7.4 per strategy_engine

---

## DD-9. Filesystem Artifacts

### DD-9.1 Production Artifacts
```
data/production/
├── orders/
│   └── orders_<timestamp>.json
├── forecasts/
│   ├── forecast_<timestamp>.json
│   └── kpi_forecast_<timestamp>.json
├── postcasts/
│   ├── postcast_<timestamp>.json
│   └── kpi_postcast_<timestamp>.json
└── kpi/
    └── kpi_<timestamp>.json
```

### DD-9.2 Backtest Artifacts
```
data/backtests/
├── runs/
│   └── backtest_<preset>_<timestamp>/
│       ├── kpi.json
│       ├── orders.json
│       ├── portfolio.json
│       └── trades.json
└── reports/
    └── backtest_summary_<batch_ts>.json
```

### DD-9.3 Session Reports
```
data/reports/sessions/<timestamp>/
├── 01_health_checks/
├── 02_data_quality/
├── 03_guardrails/
├── 04_risk_management/
├── 05_stress_tests/
├── 06_strategy_analysis/
├── 07_backtest_validation/
└── 08_performance_summary/
```

---

## DD-10. Changelog v10.8.0

**Modifiche Schema:**
- `fiscal_ledger`: Aggiunti campi audit trail (`decision_path`, `reason_code`)
- `fiscal_ledger`: Aggiunto campo `run_type` per distinzione PRODUCTION/BACKTEST
- `fiscal_ledger`: Aggiunto campo `trade_currency` per supporto FX futuro
- `tax_loss_carryforward`: Formula zainetto ottimizzata (somme separate)

**Nuove Tabelle Documentate:**
- `daily_portfolio`: Portfolio backtest
- `execution_prices`: Vista prezzi esecuzione
- `orders`: Ordini generati
- `orders_plan`: Piano ordini con decision path
- `portfolio_summary`: Vista summary portfolio
- `position_events`: Eventi posizioni
- `position_peaks`: Peak tracking
- `position_plans`: Piani posizioni holding period

**Totale Tabelle:** 19 (15 tabelle + 4 viste)

---

## DD-11. Note Implementazione

### Holding Period Tracking
Sistema completo tracking holding period implementato in v10.7+:
- `fiscal_ledger`: 6 campi holding period
- `position_plans`: Piano holding period per simbolo
- `position_events`: Eventi extend/close
- `position_peaks`: Peak tracking per trailing stop

### Audit Trail
Sistema audit trail completo:
- `fiscal_ledger`: `decision_path`, `reason_code`, `execution_price_mode`
- `trade_journal`: Tracking segnale → esecuzione
- `orders_plan`: Decision path ordini
- `position_events`: Eventi posizioni

### Fiscalità
Sistema fiscale completo conforme DIPF §6.2:
- `tax_loss_carryforward`: Zainetto per categoria fiscale
- `fiscal_ledger`: `tax_paid`, `pmc_snapshot`
- Formula zainetto corretta (v10.8.0)

---

**Firma**: Agente Principale ETF-ITA v10.8.0  
**Data**: 2026-01-07 19:46 UTC+01:00  
**Conformità**: 100% vs schema DB reale
