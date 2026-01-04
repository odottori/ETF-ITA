# 📋 TODOLIST - Implementation Plan (ETF_ITA)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r19 — 2026-01-04  

## LEGENDA
- [🟢] DONE — testato e verificato
- [🟡] WIP — in lavorazione
- [🔴] TODO — non iniziato

---

## TL-0. EntryPoints Registry (1:1 con README)
| EP | Script/Command | Output principale | Cross-Ref |
|---|---|---|---|
| EP-01 | `scripts/setup_db.py` | DB + schema | DD-2..DD-9 |
| EP-02 | `scripts/load_trading_calendar.py` | `trading_calendar` popolata | DD-3.1 |
| EP-03 | `scripts/ingest_data.py` | `market_data` + `ingestion_audit` | DIPF §3, DD-2, DD-5 |
| EP-04 | `scripts/health_check.py` | `health_report.md` | DIPF §3.5, DD-10 |
| EP-05 | `scripts/compute_signals.py` | segnali + snapshot opz. | DIPF §4, DD-8 |
| EP-06 | `scripts/check_guardrails.py` | SAFE/DANGER + motivazione | DIPF §5 |
| EP-07 | `scripts/plan_orders.py --dry-run` | `orders.json` | DIPF §8.1 |
| EP-08 | `scripts/update_ledger.py [--commit]` | ledger aggiornato + journal | DIPF §6, DD-6/7 |
| EP-09 | `scripts/run_backtest.py` | equity curve + KPI | DIPF §7/§9 |
| EP-10 | `scripts/generate_report.py` | Run Package | DIPF §7, DD-11 |
| EP-11 | `scripts/stress_test.py` | stress report | DIPF §9.2 |
| EP-12 | `scripts/restore_db.py` | ripristino DB | DIPF §8.2 |

---

## TL-1. Fase 1 — Ciclo di fiducia (MUST)

### TL-1.1 Sanity Check post-backtest/post-run
- [🔴] Implementare `scripts/sanity_check.py` (invocato da EP-09/EP-10)
- DoD: fallisce (exit!=0) se:
  - posizioni negative o cash incoerente
  - no-future-data-leak violato
  - gap su giorni `is_open=TRUE`
  - mismatch ledger vs market_data (symbol/date)

### TL-1.2 Dry-Run JSON diff-friendly
- [🔴] EP-07 produce `orders.json` con: orders, cash impact, tax estimate, guardrails state
- DoD: nessuna scrittura su ledger; output deterministico dato stesso input.

### TL-1.3 Risk Continuity Report automatico
- [🔴] Generare `risk_continuity.md` se missing > N giorni open
- DoD: trigger automatico post-ingest + link in Run Package.

### TL-1.4 Cash Interest (MUST)
- [🔴] Eventi `INTEREST` mensili in ledger
- DoD: test unitario su cash_balance con rate; verifica rounding.

### TL-1.5 KPI snapshot + kpi_hash
- [🔴] `metric_snapshot` aggiornato post-ingest/backtest
- DoD: `kpi_hash` cambia se cambia uno dei KPI principali.

---

## TL-2. Fase 2 — Reale & difendibile (MUST/SHOULD)

### TL-2.1 Fiscalità: tax_category asimmetria ETF (CRITICO)
- [🔴] Aggiungere `tax_category` in registry/config
- [🔴] Fiscal engine:
  - se `OICR_ETF` e gain>0 → tassa 26% piena, **non** usare zainetto
  - se loss<0 → crea bucket (zainetto)
  - se `ETC_ETN_STOCK` → offset con zainetto consentito
- DoD: test con sequenza BUY/SELL gain su ETF: tax_paid = gain*0.26 anche con bucket disponibile.

### TL-2.2 FX (solo se `fx_enabled=true`)
- [🔴] Tabella `fx_rates` + ingestion giornaliera
- [🔴] Ledger salva `exchange_rate_used` e `price_eur`
- DoD: test con due date FX diverse: gain EUR cambia anche a prezzo invariato.

### TL-2.3 close vs adj_close (ledger vs signals)
- [🔴] Ingestion salva **entrambi** `close` e `adj_close`
- [🔴] Valorizzazione portafoglio: `close`
- [🔴] Indicatori: `adj_close`
- DoD: test smoke su ETF DIST: price drop non “compensato” artificialmente in ledger.

### TL-2.4 Dividendi DIST (lean)
- [🔴] Se `dist_policy=DIST` e dividend disponibile → evento `DIVIDEND` in ledger con tax immediata
- DoD: warning se DIST ma dividend non modellato.

### TL-2.5 Inerzia “tax-friction aware”
- [🔴] Implementare `inertia_threshold` nel strategy engine
- DoD: scenario dove alpha atteso < costi → HOLD.

### TL-2.6 “Zombie data” detection
- [🔴] Health check: close ripetuto + volume=0 su giorno open
- DoD: tali giorni esclusi da vol/risk_metrics; warning in report.

### TL-2.7 Maintenance DuckDB
- [🔴] Script `maintenance_db.py` esegue `CHECKPOINT`
- DoD: comando idempotente; log in `maintenance_log` (opzionale) o file.

---

## TL-3. Fase 3 — Refinements (SHOULD/COULD)

### TL-3.1 Emotional Gap nel report
- [🔴] In `summary.md`: PnL “pura” vs “reale” e delta
- DoD: se delta < 0 evidenziare esplicitamente in output.

### TL-3.2 Benchmark snapshot + after-tax view
- [🔴] Materializzare `benchmark_snapshot`
- DoD: KPI benchmark in EUR disponibili senza ricalcolo pesante.

### TL-3.3 Cash-equivalent ticker (feature flag)
- [🔴] Se abilitato: parcheggio liquidità su ticker monetario
- DoD: non rompe fiscal engine; contabilizza come strumento standard.

