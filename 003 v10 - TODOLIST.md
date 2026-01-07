# TODOLIST - Implementation Plan (ETF_ITA)

**Package:** v10.8.0 (naming canonico)  
**Doc Revision:** r40 — 2026-01-07  
**Baseline produzione:** EUR / ACC  
**System Status:** BACKTEST-READY v10.8.0 + DECISION SUPPORT (non autonomous production)  
**Backtest Engine:** EVENT-DRIVEN (day-by-day, SELL→BUY priority, cash management realistico)  
**Strategy Engine V2:** TWO-PASS (Exit → Cash Update → Entry con ranking candidati)  
**Holding Period:** DINAMICO (5-30 giorni, logica invertita momentum)  
**Portfolio Construction:** IMPLEMENTATO (ranking + constraints + allocation deterministico)  
**Pre-Trade Controls:** HARD CHECKS (cash e position verification prima di ledger write)  
**Fiscal Engine:** COMPLETO (zainetto per categoria fiscale, scadenza 31/12+4 anni)  
**Auto-Update:** PROATTIVO (ingest + compute automatico, data freshness check)  
**Market Calendar:** INTELLIGENTE (festività + auto-healing chiusure eccezionali)  
**Schema DB:** 19 tabelle (15 tabelle + 4 viste) - 100% documentato  
**Schema Coherence:** VERIFIED BY test_schema_validation.py (contract validation)  
**Schema Contract:** VERIFIED BY docs/schema/SCHEMA_CONTRACT.json (v003)

## LEGENDA
- [🟢] VERIFIED — testato e verificato (con gate command)
- [🟡] CANDIDATE — parzialmente implementato (missing verification)
- [🔴] TODO — non iniziato (ARCHIVED/PLANNED)
- [🛡️] RISK — gestione rischio verificata
- [🧾] FISCAL — logica fiscale verificata
- [📊] PORTFOLIO — portfolio construction verificata
- [⚡] ENHANCED — funzionalità avanzata verificata

---

## TL-0. EntryPoints Registry (1:1 con README)
| EP | Script/Command | Output principale | Cross-Ref | Status |
|---|---|---|---|---|
| EP-01 | `scripts/setup/setup_db.py` | Crea `data/etf_data.duckdb` + schema | DD-2..DD-12 | [🟢] VERIFIED |
| EP-02 | `scripts/setup/load_trading_calendar.py` | Popola `trading_calendar` (2020-2026) | DD-3.1 | [🟢] VERIFIED |
| EP-03 | `scripts/data/ingest_data.py` | `market_data` + `ingestion_audit` | DIPF §1.2, §3 | [🟢] VERIFIED |
| EP-04 | `scripts/quality/health_check.py` | `health_report.md` | DIPF §3.5, DD-10 | [🟢] VERIFIED |
| EP-05 | `scripts/data/compute_signals.py` | segnali + snapshot | DD-6 | [🟢] VERIFIED |
| EP-05b | `scripts/data/compute_signals.py --preset <full|recent|covid|gfc|eurocrisis|inflation2022>` | segnali periodo (preset) | DIPF §4 | [🟡] CANDIDATE |
| EP-05c | `scripts/data/compute_signals.py --all` | segnali full+recent+critici | DIPF §4 | [🟡] CANDIDATE |
| EP-06 | `scripts/risk/check_guardrails.py` | SAFE/DANGER + motivazioni | DIPF §5.3 | [🟢] VERIFIED |
| EP-07 | `scripts/trading/strategy_engine.py --dry-run` | `data/orders.json` | DIPF §4.2 | [🟢] VERIFIED |
| EP-07b | `scripts/trading/strategy_engine_v2.py` | TWO-PASS workflow + holding period | DIPF §4.2, §4.3 | [🟢] VERIFIED |
| EP-08 | `scripts/trading/execute_orders.py --commit` | Esecuzione ordini con pre-trade controls | DIPF §5.2 | [🟢] VERIFIED |
| EP-09 | `scripts/orchestration/run_complete_cycle.py --dry-run` | Ciclo completo simulato | DIPF §8.3 | [🟡] CANDIDATE |
| EP-10 | `scripts/orchestration/run_complete_cycle.py --commit` | Ciclo completo esecuzione | DIPF §8.4 | [🟡] CANDIDATE |
| EP-11 | `scripts/trading/update_ledger.py --commit` | ledger + tax buckets | DIPF §6, DD-5.1 | [🟢] VERIFIED |
| EP-12 | `scripts/reports/stress_test.py` | stress report | DIPF §9.2 | [🟢] VERIFIED |
| EP-13 | `scripts/quality/sanity_check.py` | sanity check bloccante | DIPF §9.1 | [🟢] VERIFIED |
| EP-14 | `scripts/reports/performance_report_generator.py` | report performance sessione | System Test | [🟢] VERIFIED |
| EP-15 | `scripts/backtest/backtest_runner.py` | Run Package completo | DIPF §7, §9 | [🟢] VERIFIED |
| EP-15b | `scripts/backtest/backtest_runner.py --preset <full|recent|covid|gfc|eurocrisis|inflation2022>` | Run Package periodo (preset) | DIPF §7, §9 | [🟡] CANDIDATE |
| EP-15c | `scripts/backtest/backtest_runner.py --all` | Run Package full+recent+critici | DIPF §7, §9 | [🟡] CANDIDATE |
| EP-16 | `scripts/backtest/backtest_engine.py` | Simulazione event-driven realistica | DIPF §7 | [🟢] VERIFIED |
| 🛡️ | `scripts/risk/enhanced_risk_management.py` | risk management avanzato | DIPF §5.4 | [🟢] VERIFIED |
| 🧾 | `scripts/trading/execute_orders.py` | pre-trade controls + fiscal integration | DIPF §6 | [🟢] VERIFIED |
| 🧾 | `scripts/fiscal/tax_engine.py` | tassazione italiana completa + zainetto | DIPF §6.1-6.3 | [🟢] VERIFIED |
| 🛑 | `scripts/risk/trailing_stop_v2.py` | trailing stop con peak tracking | DIPF §5.4 | [🟢] VERIFIED |
| 📊 | `scripts/strategy/portfolio_construction.py` | holding period + ranking + constraints | DIPF §4.3 | [🟢] VERIFIED |
| 🔒 | `scripts/quality/schema_contract_gate.py` | gate operativo bloccante | Schema Contract | [🔴] TODO |

---

## TL-1. Fase 1 — Ciclo di fiducia

### TL-1.1 Sanity check post-run (bloccante)
- [🟢] **VERIFIED** `scripts/quality/sanity_check.py` (9 controlli bloccanti)
- DoD: exit!=0 se posizioni negative, cash negativo, invarianti violate, future data leak, calendar gaps, coherence issues

### TL-1.2 Strategy Engine V2 TWO-PASS
- [🟢] **COMPLETATO** `scripts/trading/strategy_engine_v2.py` con:
  - **PASS 1 - EXIT/SELL**: MANDATORY exits (RISK_OFF, stop-loss, planned exits)
  - **CASH UPDATE**: Simula cash post-sell per entry allocation realistica
  - **PASS 2 - ENTRY/REBALANCE**: Ranking candidati + constraints + allocation
  - Output: `orders_plan` table con `decision_path`, `reason_code`, `candidate_score`, `reject_reason`
- DoD: Workflow deterministico, audit trail completo, pre-trade checks integrati.

### TL-1.2b Holding Period Dinamico
- [🟢] **COMPLETATO** `scripts/strategy/portfolio_construction.py` con:
  - Range: 5-30 giorni (swing trading multi-day)
  - Logica INVERTITA: alto momentum/risk/vol → holding CORTO (prendi profitto veloce)
  - Adjustments: risk_adj, vol_adj, momentum_adj
  - Schema DB: `fiscal_ledger` (6 campi), `position_plans`, `position_events`, `position_peaks`
- DoD: Tracking completo holding period, extend/close con motivo, peak tracking per trailing stop.

### TL-1.2c Portfolio Construction
- [🟢] **COMPLETATO** `scripts/strategy/portfolio_construction.py` con:
  - `calculate_candidate_score()`: momentum + risk_scalar - cost_penalty - overlap_penalty
  - `rank_candidates()`: Ranking deterministico
  - `filter_by_constraints()`: Max positions, cash reserve, overlap underlying
  - `calculate_qty()`: Allocazione deterministico + rounding
- DoD: Allocation trasparente, reject logging, constraints hard verificati.

### TL-1.3 Cash interest
- [🟢] **COMPLETATO** `scripts/trading/update_ledger.py` con:
  - cash interest mensile (2% annualizzato)
  - accrual giornaliero su cash balance
  - posting mensile su `cash_interest` account
  - tax bucket OICR_ETF (26%) su interest

### TL-1.4 Risk continuity
- [🟢] **COMPLETATO** `scripts/risk/enhanced_risk_management.py` con:
  - drawdown monitoring (10%/15% thresholds)
  - volatility regime detection
  - risk scalar adjustment
  - reporting continuity metrics

### TL-1.5 KPI snapshot
- [🟢] **VERIFIED** `scripts/reports/performance_report_generator.py` (report completo)
- DoD: portfolio value, performance metrics, risk metrics, tax summary, hash verification

### TL-1.6 EUR/ACC gate
- [🟢] **COMPLETATO** Validazione baseline EUR/ACC:
  - `scripts/data/ingest_data.py` (blocco strumenti non-EUR)
  - `scripts/setup/setup_db.py` (validazione universe)
- DoD: strumenti non-EUR o DIST rifiutati con warning.

### TL-1.7 Pre-Trade Controls
- [🟢] **COMPLETATO** `scripts/trading/execute_orders.py` con:
  - `check_cash_available()`: Verifica cash sufficiente prima di BUY (inclusi commissioni + slippage)
  - `check_position_available()`: Verifica posizione sufficiente prima di SELL
  - Reject logging: Ogni trade rifiutato loggato con motivazione
- DoD: Ledger non "sporcato" con trade non eseguibili, controlli HARD prima di write.

### TL-1.8 Backtest Event-Driven
- [🟢] **COMPLETATO** `scripts/backtest/backtest_engine.py` con:
  - Loop day-by-day su trading_dates
  - SELL priority (PASS 1) → BUY (PASS 2)
  - Pre-trade controls integrati
  - Calcolo costi realistici: commission + slippage (volatility-adjusted)
  - Tassazione integrata: `calculate_tax()` per SELL
  - Portfolio value tracking + equity curve (`daily_portfolio` table)
- DoD: Simulazione realistica, cash management accurato, KPI difendibili.

### TL-1.9 Fiscal Engine Completo
- [🟢] **COMPLETATO** `scripts/fiscal/tax_engine.py` con:
  - `calculate_tax()`: Tassazione 26% con zainetto per categoria fiscale
  - `create_tax_loss_carryforward()`: Zainetto con scadenza 31/12/(anno+4)
  - `update_zainetto_usage()`: Aggiornamento used_amount FIFO
  - `get_available_zainetto()`: Query zainetto disponibile per categoria
  - Logica OICR_ETF vs ETC_ETN_STOCK conforme DIPF §6.2
- DoD: Fiscalità italiana completa, zainetto per categoria, scadenza corretta.

---

## TL-2. Fase 2 — Realismo fiscale e coerenza dati

### TL-2.1 Categoria fiscale (OICR_ETF vs ETC/ETN)
- [🟢] **COMPLETATO** `scripts/trading/execute_orders.py` (logica tax_category)
- DoD: test con gain ETF + zainetto presente → nessuna compensazione.

### TL-2.2 Zainetto: scadenza corretta 31/12 (anno+4)
- [🟢] **COMPLETATO** `scripts/fiscal/update_tax_loss_carryforward.py` (expires_at formula)
- DoD: test con realize 05/01/2026 → expires 31/12/2030.

### TL-2.3 close vs adj_close (coerenza)
- [🔴] **TODO** `scripts/quality/check_price_convention.py` (non presente)
- DoD: test che impedisce uso `adj_close` in valuation ledger.

### TL-2.4 Zombie/stale prices (health + risk metrics)
- [🟢] **COMPLETATO** `scripts/quality/zombie_exclusion_enforcer.py` (esclusione KPI)
- DoD: risk metrics escludono giorni ZOMBIE dal calcolo della volatilità.

### TL-2.5 Run Package completo (manifest/kpi/summary)
- [🟢] **VERIFIED** `EP-15` produce manifest/kpi/summary completi
- DoD: mancanza file → exit!=0; manifest include config_hash e data_fingerprint.

### TL-2.6 Spike threshold per simbolo (max_daily_move_pct)
- [🟢] **COMPLETATO** `scripts/quality/spike_detector.py` (threshold dinamici)
- DoD: test su simbolo con soglia più stretta (es. 10%) e su simbolo default 15%.

### TL-2.7 Benchmark after-tax corretto (INDEX vs ETF)
- [🟢] **COMPLETATO** `manifest_*.json` con `benchmark_kind: INDEX`
- DoD: KPI benchmark non distorti; `manifest.json` esplicita `benchmark_kind`.

---

## TL-3. Fase 3 — "Smart retail" e UX

### TL-3.1 Inerzia tax-friction aware
- [🟢] **COMPLETATO** In strategy_engine: logica MANDATORY vs OPPORTUNISTIC
- DoD: scenario test dove "fare nulla" è scelta ottimale.

### TL-3.2 Emotional Gap in summary.md
- [🟢] **COMPLETATO** Calcolo PnL "puro" vs "reale" implementato in performance_report_generator.py
- DoD: gap calcolato e mostrato con warning se costi elevati (>€100).

### TL-3.3 Cash-equivalent ticker (feature flag)
- [🔴] TODO Se `cash_equivalent_enabled=true`: parcheggio liquidità su ticker monetario
- DoD: disattivato di default; attivabile solo se universe ammette il ticker e fiscalità è gestita.

---

## TL-4. Fase 4 — Risk Management Avanzato

### TL-4.1 Enhanced Risk Management
- [🟢] **COMPLETATO** `scripts/risk/enhanced_risk_management.py` con:
  - Volatility > 15%: risk scalar ridotto del 70%
  - Volatility > 20%: risk scalar ridotto del 90%
  - Zombie price detection automatica
  - Protezione specifica per ETF ad alto rischio (XS2L.MI)

### TL-4.2 Trailing Stop V2
- [🟢] **COMPLETATO** `scripts/risk/trailing_stop_v2.py` con:
  - Peak tracking post-entry
  - Drawdown calcolato da peak_price
  - Configurazione flessibile drawdown_threshold
  - Logica min_profit_activation

### TL-4.3 Pre-Trade Controls
- [🟢] **COMPLETATO** `scripts/trading/execute_orders.py` con:
  - check_cash_available() prima di BUY
  - check_position_available() prima di SELL
  - Reject logging strutturato
  - Controlli hard bloccanti

---

## TL-5. Fase 5 — Schema Coherence

### TL-5.1 Schema Contract
- [🟢] **COMPLETATO** `scripts/quality/schema_contract_gate.py` implementato
- DoD: validazione formale vs docs/schema/v003/SCHEMA_CONTRACT.json, gate bloccante con strict mode

### TL-5.2 Schema Coherence Enforcement
- [🟢] **COMPLETATO** Validazione integrata in schema_contract_gate.py
- DoD: validazione tabelle/colonne/tipi vs contract, report dettagliato errori/warnings

---

## TL-6. Fase 6 — Utility & Operations

### TL-6.1 Scripts Organization
- [🟢] **COMPLETATO** Struttura riorganizzata v10.8 con:
  - scripts/setup/: 2 file (setup_db, load_trading_calendar)
  - scripts/data/: 3 file (ingest, signals, extend)
  - scripts/trading/: 3 file (strategy, execute, ledger)
  - scripts/backtest/: 2 file (engine, runner)
  - scripts/quality/: 6 file (health, sanity, audit, spike, zombie, schema_gate)
  - scripts/risk/: 6 file (guardrails, controls, enhanced, diversification, vol, trailing)
  - scripts/fiscal/: 1 file (tax_engine)
  - scripts/reports/: 3 file (performance, stress, production_kpi)
  - scripts/orchestration/: 3 file (sequence, session, automated_test)
  - scripts/utils/: 3 file (path_manager, market_calendar, console_utils)
  - scripts/maintenance/: 3 file (update_calendar, backup_db, restore_db)

### TL-6.2 Documentation Management
- [🟢] **COMPLETATO** Documenti canonici v003:
  - AGENT_RULES: regole operative
  - PROJECT_OVERVIEW: visione sistema
  - DIPF: design framework
  - DATADICTIONARY: schema dati
  - README: comandi operativi

### TL-6.3 Backup & Maintenance
- [🟢] **COMPLETATO** `scripts/maintenance/backup_db.py` (backup automatico con validazione)
- [🟢] **COMPLETATO** `scripts/maintenance/restore_db.py` (ripristino con safety backup)
- [🟢] **COMPLETATO** `scripts/maintenance/update_market_calendar.py` (già esistente)

---


---

## PROGETTO PRONTO PER PRODUZIONE v003

**Framework completo e robusto con:**
- Dati certificati 2010-2026
- Risk management completo con Enhanced Risk Management
- Fiscal engine italiano conforme DIPF §6.2
- Run package serializzato
- Sanity check bloccante
- Smart retail features
- Schema coherence enforcement
- Scripts organization pulita (17+2+0 file)
- Documenti canonici v003 coordinati
- Pre-trade controls hardcoded
- Momentum score refactor completato
- Trailing stop V2 con peak tracking

**Pronto per backtest e decision support con semaforica coordinata.**
