# PROJECT_OVERVIEW — ETF_ITA Smart Retail

## 1. Missione del Progetto
Costruire un sistema EOD "smart retail" per residenti italiani, focalizzato su:
- affidabilità operativa (audit, sanity, guardrails)
- realismo fiscale (PMC, tassazione 26%, zainetto)
- reporting netto e riproducibile (Run Package)
- disciplina decisionale (Signal Engine oggettivo)

## 1.1 Stato Sistema
- **Stato Sistema**: BACKTEST-READY v10.8.0 + DECISION SUPPORT (non autonomous production)
- **Version**: r40 — 2026-01-07

**Stato Reale**: Sistema robusto per backtest e decision support con human-in-the-loop. Non ancora autonomous production.

**Gap Production Rimanenti**:
- Execution bridge broker reale (manca integrazione API broker)
- Monitoring/alerting automatico (nessun sistema attivo)
- Disaster recovery automatico (backup manuali)
- Logging strutturato enterprise-grade
- Performance testing carico reale
- Security: secrets management, API keys encryption

- **Components**: 
  - Signal Engine (compute_signals.py)
  - Strategy Engine V2 (strategy_engine_v2.py) - TWO-PASS workflow
  - Portfolio Construction (portfolio_construction.py) - Holding period dinamico
  - Execute Orders (execute_orders.py) - Pre-trade controls
  - Backtest Engine (backtest_engine.py) - Event-driven simulation
  - Fiscal Engine (tax_engine.py) - Tassazione italiana completa
  - Session Manager (session_manager.py) - Report serializzati
  - Risk Metrics (vista DB) - Window functions
- **Backtest Engine**: EVENT-DRIVEN (day-by-day, SELL→BUY priority, cash management realistico)
- **Strategy Engine V2**: TWO-PASS (Exit → Cash Update → Entry con ranking candidati)
- **Holding Period**: DINAMICO (5-30 giorni, logica invertita momentum)
- **Pre-Trade Controls**: HARD CHECKS (cash e position verification)
- **Fiscal Engine**: COMPLETO (zainetto per categoria fiscale, scadenza 31/12+4 anni)
- **Auto-Update**: PROATTIVO (ingest + compute automatico, data freshness check)
- **Market Calendar**: INTELLIGENTE (festività + auto-healing chiusure eccezionali)
- **Schema DB**: 19 tabelle (15 tabelle + 4 viste) - 100% documentato

### Verification Gates
Gate reali (script esistenti nel repo):

- **Unit/Integration Gate (pytest)**: `py -m pytest -q`
- **Data Quality Gate (health_check)**: `py scripts/quality/health_check.py`
- **Risk Gate (guardrails)**: `py scripts/risk/check_guardrails.py`
- **Accounting Gate (sanity_check)**: `py scripts/quality/sanity_check.py`
- **Schema Contract Gate (schema_validation)**: `py -m pytest -q tests/test_schema_validation.py`

## 2. Architettura
- DB: DuckDB (`data/etf_data.duckdb`)
- Runtime: Python 3.10+
- Storage: Parquet + Run Package
- OS: Windows
- Execution Model: T+1_OPEN (default)
- Cost Model: TER drag, slippage dinamico, commissioni realistiche
- Fiscal Model: Italia (OICR_ETF baseline)

## 3. Documenti Canonici
- DIPF ProjectDoc (r40 — v10.8.0) - Riconciliato con implementazione reale
- DDCT DataDictionary (r44 — v10.8.0) - Riscritto da zero su schema DB reale
- TLST ToDoList (r40 — v10.8.0) - Riconciliato con implementazione reale
- README operativo (r40 — v10.8.0) - Riconciliato con implementazione reale
- PROJECT_OVERVIEW (r40 — v10.8.0) - Riconciliato
- AGENT_RULES (v10.5.0)

## 4. Requisiti Funzionali (IMPLEMENTATI)
- RF-01: ✅ Ingestione dati EOD con audit (ingest_data.py)
- RF-02: ✅ Health check completo (health_check.py)
- RF-03: ✅ Signal engine oggettivo (compute_signals.py)
- RF-04: ✅ Guardrails e risk management (check_guardrails.py, enhanced_risk_management.py)
- RF-05: ✅ Strategy engine V2 TWO-PASS (strategy_engine_v2.py)
- RF-06: ✅ Ledger fiscale con PMC (fiscal_ledger 26 colonne)
- RF-07: ✅ Run Package serializzato (session_manager.py)
- RF-08: ✅ Stress test (stress_test.py)
- RF-09: ✅ Sanity check bloccante (sanity_check.py)
- RF-10: ✅ Session manager (session_manager.py)
- RF-11: ✅ Benchmark after-tax (risk_metrics vista)
- RF-12: ✅ EUR/ACC gate (symbol_registry validation)
- RF-13: ✅ Zombie price exclusion (spike_detector.py, zombie_exclusion_enforcer.py)
- RF-14: ✅ Spike detection per simbolo (spike_detector.py)
- RF-15: ✅ Cash interest mensile (update_ledger.py)
- RF-16: ✅ Journaling forecast/postcast (trade_journal, orders_plan)
- RF-17: ✅ Tax-friction aware logic (candidate_score con cost_penalty)
- RF-18: ✅ Holding period dinamico (5-30 giorni, portfolio_construction.py)
- RF-19: ✅ Pre-trade controls (check_cash_available, check_position_available)
- RF-20: ✅ Backtest event-driven (backtest_engine.py)
- RF-21: ✅ Fiscal engine completo (tax_engine.py - zainetto per categoria)
- RF-22: ✅ Portfolio construction (ranking candidati + constraints)
- RF-23: ✅ Position management (position_plans, position_events, position_peaks)
- RF-24: ✅ Execution prices vista (close per valorizzazione)
- RF-25: ✅ Risk metrics vista (window functions + close/volume)

## 5. Requisiti Non Funzionali
- RNF-01: riproducibilità totale
- RNF-02: determinismo a parità di input
- RNF-03: performance retail-grade
- RNF-04: coerenza fiscale
- RNF-05: auditabilità completa
- RNF-06: robustezza contro dati errati
- RNF-07: documentazione auto-consistente

## 6. Standard Qualità
Ogni modifica deve includere:
- test unitari (sempre, indispensabili per regressioni)
- test integrazione (sempre, previene disastri nel 10% dei casi critici)
- aggiornamento snapshot (solo per modifiche KPI)
- lint/format (sempre - formattazione codice standardizzata)
- controllo aggiornamento documentazione / semaforica + cross reference (sempre, tassativo)

### Quality Gates
- **Unit/Integration Test Gate**: `py -m pytest -q`
- **Documentation Gate**: (canonici: DIPF/DDCT/TLST/README) review + cross-check manuale

## 7. Output Obbligatori
- manifest.json
- kpi.json
- summary.md
- orders.json
- audit ingestione
- stress test
- sanity check

## 8. Architettura Scripts (REALE)
- **scripts/setup/**: Setup & initialization (4 file)
- **scripts/data/**: Data pipeline (3 file)
- **scripts/trading/**: Strategy & execution (5 file)
- **scripts/backtest/**: Backtesting (3 file)
- **scripts/quality/**: Data quality & health (7 file)
- **scripts/risk/**: Risk management (7 file)
- **scripts/fiscal/**: Tax & fiscal (2 file)
- **scripts/reports/**: Reports & analysis (3 file)
- **scripts/orchestration/**: Workflow orchestration (4 file)
- **scripts/utils/**: Shared utilities (4 file)
- **scripts/maintenance/**: Maintenance scripts (3 file)
- **scripts/analysis/**: Analysis tools (6 file)
- **scripts/strategy/**: Strategy modules (1 file)
- **scripts/temp/**: Temporary scripts (4 file)
- **scripts/archive/**: Historical scripts (0 file)

**Totale**: 53 file Python
- **tests/**: Suite test
- **scripts/temp/**: File temporanei da pulire

## 9. Organizzazione File
- **REGOLA CRITICA**: MAI creare file .py nella root del progetto
- Tutti i file .py devono essere creati in scripts/core, scripts/utility, scripts/temp o tests/
- La root contiene solo documenti canonici e configurazione
