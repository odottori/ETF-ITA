# 📚 DATADICTIONARY (ETF_ITA)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r19 — 2026-01-04  
**Database:** DuckDB embedded (`data/etf_data.duckdb`)

---

## DD-0. Principi
- Tipi numerici di mercato: `DOUBLE` (performance).  
- Valori contabili: arrotondare a 2 decimali in query/report (no cast pervasivi).  
- Date: `DATE` nativo.  
- Tutte le tabelle principali includono `created_at` e `last_updated`.

---

## DD-1. Storage fisico
- **Path:** `data/etf_data.duckdb`  
- **Backup:** `data/backup/` (Parquet o copia file)  
- **Report serializzati:** `data/reports/<run_id>/`

---

## DD-2. Tabelle dati di mercato

### DD-2.1 `market_data`
Serie storica prezzi EOD.

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | PK (composita) |
| date | DATE | PK (composita) |
| close | DOUBLE | Prezzo raw (ledger valuation) |
| adj_close | DOUBLE | Prezzo adjusted (signals/returns) |
| volume | BIGINT | >=0 |
| currency | VARCHAR | Es. EUR, USD |
| provider | VARCHAR | Es. YF, TIINGO |
| last_updated | TIMESTAMP | default now() |
| created_at | TIMESTAMP | default now() |

**PK:** (`symbol`, `date`)

### DD-2.2 `corporate_actions` (opzionale, warning-only)
| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | |
| date | DATE | |
| type | VARCHAR | 'DIVIDEND'/'SPLIT' |
| amount | DOUBLE | €/share o ratio |
| source | VARCHAR | |
| created_at | TIMESTAMP | |

**PK:** (`symbol`, `date`, `type`)

---

## DD-3. Trading calendar e registry strumenti

### DD-3.1 `trading_calendar`
| Colonna | Tipo | Note |
|---|---|---|
| venue | VARCHAR | 'BIT'/'XETRA'/etc |
| date | DATE | |
| is_open | BOOLEAN | |
| created_at | TIMESTAMP | |

**PK:** (`venue`, `date`)

### DD-3.2 `symbol_registry`
Anagrafica strumenti e gestione ticker-change/survivorship (lean).

| Colonna | Tipo | Note |
|---|---|---|
| symbol | VARCHAR | PK |
| parent_symbol | VARCHAR | mapping/alias (opzionale) |
| status | VARCHAR | ACTIVE/STALLED/DELISTED |
| asset_class | VARCHAR | EQUITY_ETF/BOND_ETF/ETC/STOCK/... |
| dist_policy | VARCHAR | ACC/DIST |
| tax_category | VARCHAR | OICR_ETF / ETC_ETN_STOCK |
| base_currency | VARCHAR | valuta quotazione |
| notes | VARCHAR | |
| created_at | TIMESTAMP | |
| last_updated | TIMESTAMP | |

---

## DD-4. FX

### DD-4.1 `fx_rates`
Tassi giornalieri (solo se `fx_enabled=true`).

| Colonna | Tipo | Note |
|---|---|---|
| pair | VARCHAR | es. 'USD/EUR' |
| date | DATE | |
| rate | DOUBLE | 1 unit base in quote |
| source | VARCHAR | |
| created_at | TIMESTAMP | |

**PK:** (`pair`, `date`)

---

## DD-5. Audit ingestione

### DD-5.1 `ingestion_audit`
| Colonna | Tipo | Note |
|---|---|---|
| audit_id | VARCHAR | PK (uuid) |
| provider | VARCHAR | |
| venue | VARCHAR | |
| start_date | DATE | |
| end_date | DATE | |
| rows_fetched | INTEGER | |
| rows_accepted | INTEGER | |
| rows_rejected | INTEGER | |
| reject_summary | VARCHAR | |
| revision_tol_pct | DOUBLE | default 0.005 |
| provider_schema_hash | VARCHAR | |
| created_at | TIMESTAMP | |

---

## DD-6. Fiscalità e ledger

### DD-6.1 `fiscal_ledger`
Registro operazioni e cash. **Fonte di verità** contabile.

| Colonna | Tipo | Note |
|---|---|---|
| id | BIGINT | PK |
| run_id | VARCHAR | link a run package |
| date | DATE | trade date |
| type | VARCHAR | BUY/SELL/INTEREST/DIVIDEND |
| symbol | VARCHAR | |
| qty | DOUBLE | quote |
| price | DOUBLE | prezzo nella valuta di quotazione |
| trade_currency | VARCHAR | es. EUR/USD |
| exchange_rate_used | DOUBLE | verso EUR (1 trade_ccy in EUR) |
| price_eur | DOUBLE | price * fx |
| cash_delta_eur | DOUBLE | variazione cassa in EUR |
| pmc_eur | DOUBLE | PMC medio in EUR (post trade) |
| realized_pnl_eur | DOUBLE | solo SELL |
| tax_category | VARCHAR | copia da registry al momento trade |
| tax_paid_eur | DOUBLE | imposta pagata |
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
| entry_reason | VARCHAR | forecast |
| expected_risk_pct | DOUBLE | es. -0.07 |
| signal_state_entry | VARCHAR | |
| risk_scalar_entry | DOUBLE | |
| theoretical_price | DOUBLE | open/close teorico |
| realized_price | DOUBLE | se disponibile |
| slippage_bps | DOUBLE | calcolato |
| flag_override | BOOLEAN | default FALSE |
| override_reason | VARCHAR | required if override |
| exit_reason | VARCHAR | postcast |
| realized_pnl_pct | DOUBLE | |
| holding_days | INTEGER | |
| market_state_json | JSON | optional (default NULL) |
| execution_quality_score | DOUBLE | |
| created_at | TIMESTAMP | |
| last_updated | TIMESTAMP | |

---

## DD-8. Metriche e snapshot

### DD-8.1 `metric_snapshot`
Snapshot KPI portafoglio (periodico, post-ingestion).

| Colonna | Tipo | Note |
|---|---|---|
| snapshot_id | VARCHAR | PK |
| as_of_date | DATE | |
| cagr | DOUBLE | |
| max_dd | DOUBLE | |
| vol | DOUBLE | |
| sharpe | DOUBLE | |
| turnover | DOUBLE | |
| kpi_hash | VARCHAR | hash KPI |
| created_at | TIMESTAMP | |

### DD-8.2 `benchmark_snapshot`
KPI benchmark comparabile (EUR, proxy after-tax).

| Colonna | Tipo | Note |
|---|---|---|
| snapshot_id | VARCHAR | PK |
| as_of_date | DATE | |
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
Indice delle run e percorsi report.

| Colonna | Tipo | Note |
|---|---|---|
| run_id | VARCHAR | PK |
| run_ts | TIMESTAMP | |
| mode | VARCHAR | BACKTEST/LIVE_SIM/DRY_RUN |
| config_hash | VARCHAR | |
| kpi_hash | VARCHAR | |
| status | VARCHAR | OK/FAIL |
| report_path | VARCHAR | |
| created_at | TIMESTAMP | |

---

## DD-10. Views (output ergonomico)

### DD-10.1 `portfolio_overview`
Per simbolo: qty, pmc_eur, last_close_eur, unrealized_pnl_eur, value_eur.

### DD-10.2 `trade_actions_log`
Join `fiscal_ledger` + `trade_journal` per audit motivazioni.

### DD-10.3 `benchmark_after_tax_eur`
Benchmark convertito EUR + proxy costi/tasse per confronto “apples-to-apples”.

---

## DD-11. Run Package (filesystem artifacts)

### DD-11.1 `manifest.json` (minimo)
- run_id, run_ts, mode
- execution_model, cost model, tax model
- universe (symbol, dist_policy, tax_category, currency)
- data_window
- data provenance (provider, audit_id)
- db_path + optional “data fingerprint” (rowcount per symbol + max(date))

### DD-11.2 `kpi.json` (minimo)
- KPI principali + kpi_hash
- breakdown costi: tax_paid_total, fees_total, slippage_est

### DD-11.3 `summary.md`
Sintesi leggibile + sezione “Emotional Gap” (pura vs reale).
