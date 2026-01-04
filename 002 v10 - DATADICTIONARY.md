# 📚 DATADICTIONARY (ETF_ITA)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r20 — 2026-01-04  
**Database:** DuckDB embedded (`data/etf_data.duckdb`)  
**Baseline produzione:** **EUR / ACC** (FX e DIST disattivati salvo feature flag)

---

## DD-0. Principi
- Tipi numerici di mercato: `DOUBLE` (performance).  
- Valori contabili: arrotondare a 2 decimali in query/report (no cast pervasivi).  
- Date: `DATE` nativo.  
- Tabelle principali: `created_at` e `last_updated`.
- Convenzione prezzi: `adj_close` per segnali, `close` per valorizzazione ledger (DIPF §2.1).
- Baseline EUR/ACC: `currency='EUR'` e `dist_policy='ACC'` per strumenti attivi; non-EUR/DIST richiedono feature flag.

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

---

## DD-6. Fiscalità e ledger

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

### DD-6.2 `tax_loss_buckets`
Minusvalenze “redditi diversi” riportabili (lean FIFO).

| Colonna | Tipo | Note |
|---|---|---|
| bucket_id | BIGINT | PK |
| created_at | TIMESTAMP | data realizzo |
| expires_at | DATE | **31/12** (anno+4) |
| amount_eur | DOUBLE | residuo compensabile |
| source_trade_id | BIGINT | link a fiscal_ledger.id |
| last_updated | TIMESTAMP | |

---

## DD-7. Trade journaling & attribution

### DD-7.1 `trade_journal`
Tabella “ombra” collegata a `fiscal_ledger` per Forecast/Postcast.  
Approccio **scalar-first**; JSON opzionale.

| Colonna | Tipo | Note |
|---|---|---|
| trade_id | BIGINT | PK (= fiscal_ledger.id) |
| run_id | VARCHAR | |
| flag_override | BOOLEAN | default FALSE |
| override_reason | VARCHAR | obbl. se override |
| entry_reason | VARCHAR | forecast |
| expected_risk_pct | DOUBLE | es. -0.07 |
| signal_state_entry | VARCHAR | RISK_ON/OFF/HOLD |
| risk_scalar_entry | DOUBLE | 0..1 |
| exit_reason | VARCHAR | postcast |
| realized_pnl_pct | DOUBLE | |
| holding_days | INTEGER | |
| theoretical_price | DOUBLE | modello esecuzione |
| realized_price | DOUBLE | se disponibile |
| slippage_bps | DOUBLE | |
| market_state_json | JSON | opzionale |
| created_at | TIMESTAMP | |
| last_updated | TIMESTAMP | |

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
| report_path | VARCHAR | `data/reports/<run_id>` |
| created_at | TIMESTAMP | |

---

## DD-10. Views (output ergonomico)

### DD-10.1 `portfolio_overview`
Vista: qty, pmc, market_value, unrealized_pnl, ecc.

### DD-10.2 `trade_actions_log`
Join `fiscal_ledger` + `trade_journal` per log motivazioni/azioni.

### DD-10.3 `benchmark_after_tax_eur`
Vista comparabile “apples-to-apples” (EUR, proxy costi/tasse), coerente con `tax_category`.

---

## DD-11. Run Package (filesystem artifacts)

### DD-11.1 `manifest.json` (minimo)
Campi obbligatori:
- `run_id`, `run_ts`, `mode`
- `execution_model`, `cost_model`, `tax_model`
- `currency_base` (EUR)
- `universe` (lista strumenti + tax_category + dist_policy)
- `config_hash`, `data_fingerprint`

### DD-11.2 `kpi.json` (minimo)
- KPI portfolio (cagr, max_dd, vol, sharpe, turnover)
- componenti costo/tasse (fees, taxes, slippage_est)
- `kpi_hash`

### DD-11.3 `summary.md`
Una pagina leggibile con:
- parametri principali
- KPI + confronto benchmark (se presente)
- sezione “Emotional Gap” (se journaling disponibile)
