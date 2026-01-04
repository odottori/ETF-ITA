# 📋 TODOLIST - Implementation Plan (ETF_ITA)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r22 — 2026-01-04  
**Baseline produzione:** **EUR / ACC**

## LEGENDA
- [🟢] DONE — testato e verificato
- [🟡] WIP — in lavorazione
- [🔴] TODO — non iniziato

---

## TL-0. EntryPoints Registry (1:1 con README)
| EP | Script/Command | Output principale | Cross-Ref | Status |
|---|---|---|---|---|
| EP-01 | `scripts/setup_db.py` | Crea `data/etf_data.duckdb` + schema | DD-2..DD-12 | ✅ DONE |
| EP-02 | `scripts/load_trading_calendar.py` | Popola `trading_calendar` | DD-3.1 | ✅ DONE |
| EP-03 | `scripts/ingest_data.py` | `market_data` + `ingestion_audit` | DIPF §1.2, §3 | ✅ DONE |
| EP-04 | `scripts/health_check.py` | `health_report.md` | DIPF §3.5, DD-10 | ✅ DONE |
| EP-05 | `scripts/compute_signals.py` | segnali + snapshot | DD-6 | ✅ DONE |
| EP-06 | `scripts/check_guardrails.py` | SAFE/DANGER + motivazioni | DIPF §5.3 | ✅ DONE |
| EP-07 | `scripts/strategy_engine.py --dry-run` | `data/orders.json` | DIPF §8.1, DD-12 | ✅ DONE |
| EP-08 | `scripts/update_ledger.py --commit` | ledger + tax buckets | DIPF §6, DD-7 | ✅ DONE |
| EP-09 | `scripts/backtest_runner.py` | Run Package completo | DIPF §7, §9 | ✅ DONE |
| EP-10 | `scripts/stress_test.py` | stress report | DIPF §9.2 | ✅ DONE |

---

## TL-1. Fase 1 — Ciclo di fiducia (MUST)
### TL-1.1 Sanity check post-run (bloccante)
- [🟢] Implementare `scripts/sanity_check.py` (invocato da EP-08/EP-09)
- DoD: exit!=0 se:
  - posizioni negative / qty < 0
  - cash/equity incoerenti (invarianti contabili)
  - violazione "no future data leak" rispetto all'execution model
  - gap su giorni `is_open=TRUE` (trading_calendar)
  - mismatch ledger vs market_data su date/symbol

### TL-1.2 Dry-run JSON diff-friendly
- [🟢] EP-07 produce `data/orders.json` con:
  - orders proposti (BUY/SELL/HOLD), qty, reason, `explain_code`
  - cash impact
  - tax estimate (se SELL o se cost model lo richiede)
  - stime: `expected_alpha_est`, `fees_est`, `tax_friction_est`
  - `do_nothing_score` + `recommendation` (HOLD/TRADE)
  - guardrails state
- DoD: nessuna scrittura su DB/ledger; output deterministico a parità input.

### TL-1.3 Cash interest (MUST)
- [🟢] Evento `INTEREST` mensile su cash_balance (fiscal_ledger)
- DoD: calcolo documentato; rounding a 0.01 EUR; inclusione nel report KPI.

### TL-1.4 Risk Continuity Report automatico
- [🟢] Generare `risk_continuity.md` se missing > N giorni open (post-ingest)
- DoD: trigger automatico; link nel Run Package.

### TL-1.5 KPI snapshot + kpi_hash
- [🟢] Popolare `metric_snapshot` e calcolare `kpi_hash`
- DoD: hash cambia se e solo se cambiano KPI canonici; include run_id.

### TL-1.6 Enforce baseline EUR/ACC (gate)
- [🟢] Validazione in ingestion/config: solo `currency=EUR` e `dist_policy=ACC`
- DoD: se rilevato non-EUR o DIST senza feature flag → blocco run (exit!=0) + messaggio chiaro.

---

## TL-2. Fase 2 — Realismo fiscale & data quality (SHOULD/MUST)
### TL-2.1 Categoria fiscale strumento (CRITICO)
- [�] Implementare `tax_category` (default `OICR_ETF`) e logica:
  - `OICR_ETF`: gain tassato pieno 26% (no zainetto)
  - `ETC_ETN_STOCK`: gain può compensare zainetto
- DoD: unit test su caso gain ETF con zainetto presente → nessuna compensazione.

### TL-2.2 Zainetto: scadenza corretta 31/12 (anno+4)
- [�] `expires_at = 31/12/(year(realize)+4)` su `tax_loss_buckets`
- DoD: test con realize 05/01/2026 → expires 31/12/2030.

### TL-2.3 close vs adj_close (coerenza)
- [�] Segnali su `adj_close`; ledger valuation su `close`
- DoD: test che impedisce uso `adj_close` in valuation ledger (query/flag).

### TL-2.4 Zombie/stale prices (health + risk metrics)
- [�] In health_check: rilevare close ripetuto + volume=0 su giorno open → flag "ZOMBIE"
- DoD: risk metrics escludono giorni ZOMBIE dal calcolo della volatilità.

### TL-2.5 Run Package completo (manifest/kpi/summary)
- [�] EP-09 deve produrre tutti gli artefatti obbligatori
- DoD: mancanza file → exit!=0; manifest include config_hash e data_fingerprint.

### TL-2.6 Spike threshold per simbolo (max_daily_move_pct)
- [�] Aggiungere `max_daily_move_pct` (default 0.15) in `etf_universe.json` e/o `symbol_registry`
- [�] In ingestion: usare la soglia specifica per scartare spike > soglia e loggare la soglia usata
- DoD: test su simbolo con soglia più stretta (es. 10%) e su simbolo default 15%.

### TL-2.7 Benchmark after-tax corretto (INDEX vs ETF)
- [�] Il reporting deve distinguere `benchmark_kind`:
  - `INDEX`: no tassazione simulata (solo friction proxy)
  - `ETF`: tassazione simulata coerente con `tax_category`
- DoD: KPI benchmark non distorti; `manifest.json` esplicita `benchmark_kind`.

---

## TL-3. Fase 3 — “Smart retail” e UX (COULD/SHOULD)
### TL-3.1 Inerzia tax-friction aware
- [�] In strategy_engine: non ribilanciare se (alpha atteso - costi) < soglia
- DoD: scenario test dove “fare nulla” è scelta ottimale.

### TL-3.2 Emotional Gap in summary.md
- [�] Calcolo PnL “puro” vs “reale” e stampa gap
- DoD: se gap < 0, evidenza forte nel summary.

### TL-3.3 Cash-equivalent ticker (feature flag)
- [�] Se `cash_equivalent_enabled=true`: parcheggio liquidità su ticker monetario
- DoD: disattivato di default; attivabile solo se universe ammette il ticker e fiscalità è gestita.

---

## TL-4. Utility & Ops (consigliate)
- [�] `scripts/backup_db.py` (backup pre-commit + CHECKPOINT)
- [�] `scripts/restore_db.py` (ripristino da backup)
- [�] `scripts/update_trading_calendar.py` (manutenzione annuale calendario)

---

## STATO IMPLEMENTAZIONE COMPLETO

### ENTRYPOINTS COMPLETATI (10/10)
- **EP-01**: Setup Database 
- **EP-02**: Trading Calendar  
- **EP-03**: Ingestion Data 
- **EP-04**: Health Check 
- **EP-05**: Compute Signals 
- **EP-06**: Check Guardrails 
- **EP-07**: Strategy Engine 
- **EP-08**: Update Ledger 
- **EP-09**: Backtest Runner 
- **EP-10**: Stress Test 

### CICLO DI FIDUCIA COMPLETO
- **TL-1.1**: Sanity check bloccante 
- **TL-1.2**: Dry-run JSON 
- **TL-1.3**: Cash interest 
- **TL-1.4**: Risk continuity 
- **TL-1.5**: KPI snapshot 
- **TL-1.6**: EUR/ACC gate 

### REALISMO FISCALE COMPLETO
- **TL-2.1**: Categoria fiscale 
- **TL-2.2**: Zainetto scadenza 
- **TL-2.3**: close vs adj_close 
- **TL-2.4**: Zombie prices 
- **TL-2.5**: Run Package 
- **TL-2.6**: Spike threshold 
- **TL-2.7**: Benchmark after-tax 

### SMART RETAIL COMPLETO
- **TL-3.1**: Inerzia tax-friction 
- **TL-3.2**: Emotional Gap 
- **TL-3.3**: Cash-equivalent 

### UTILITY COMPLETE
- **Backup/Restore**: 
- **Calendar maintenance**: 

---

## PROGETTO PRONTO PER PRODUZIONE

**Framework completo e robusto con:**
- Dati certificati 2010-2026
- Risk management completo
- Fiscal engine italiano
- Run package serializzato
- Sanity check bloccante
- Smart retail features

**Pronto per backtest e decision support.**
