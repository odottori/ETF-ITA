# 🇪🇺 ETF_ITA — Smart Retail (README)

| Meta-Dato | Valore |
| :--- | :--- |
| **Package (canonico)** | v10.8.4 |
| **Doc Revision** | r44 — 2026-01-08 |
| **Baseline Produzione** | **EUR / ACC** (solo ETF UCITS ad accumulazione in EUR) |
| **Stato Sistema** | **BACKTEST-READY v10.8.4** + **DECISION SUPPORT** + **MONTE CARLO GATE** + **CALENDAR HEALING** + **SCHEMA FIX** |
| **Scripts Funzionanti** | **53 file Python** (15 directory) |
| **Schema DB** | **19 tabelle** (15 tabelle + 4 viste) - 100% documentato |
| **Closed Loop** | **ROBUST MUTUAL EXCLUSION** (commit > dry-run, deterministic) |
| **Strategy Engine V2** | **TWO-PASS** (Exit → Cash Update → Entry con ranking candidati) |
| **Holding Period** | **DINAMICO** (5-30 giorni, logica invertita momentum) |
| **Portfolio Construction** | **IMPLEMENTATO** (ranking + constraints + allocation) |
| **Pre-Trade Controls** | **HARD CHECKS** (cash e position verification) |
| **Backtest Engine** | **EVENT-DRIVEN** (day-by-day, SELL→BUY priority, cash management realistico) |
| **Fiscal Engine** | **COMPLETO** (zainetto per categoria fiscale, scadenza 31/12+4 anni) |
| **Auto-Update** | **PROATTIVO** (ingest + compute automatico, data freshness check) |
| **Market Calendar** | **INTELLIGENTE** (festività + auto-healing chiusure eccezionali) |
| **Schema Coherence** | **DRIFT ELIMINATED** (contract unico + validation) |

---

## 1) Descrizione del sistema

Sistema EOD per gestione portafoglio ETF "risk-first" per residenti italiani, con:
- data quality gating (staging → master)
- guardrails + sizing
- ledger fiscale (PMC) + journaling (forecast/postcast)
- **session management centralizzato** con prefissi ordinali
- reporting serializzato (Run Package)

### 1.1 Caratteristiche Principali
- **Strategy Engine V2 TWO-PASS**: Exit → Cash Update → Entry con ranking candidati e constraints
- **Holding Period Dinamico**: 5-30 giorni con logica invertita (alto momentum = holding corto)
- **Portfolio Construction**: Ranking candidati + cost penalty + overlap penalty + constraints hard
- **Pre-Trade Hard Controls**: Cash e posizione verificati prima di ogni trade (no ledger "sporco")
- **Backtest Event-Driven**: Simulazione day-by-day con SELL priority, cash management realistico
- **Fiscal Engine Completo**: Tassazione 26% + zainetto per categoria fiscale (OICR_ETF vs ETC_ETN_STOCK)
- **Calendar Healing System**: Auto-correttivo per data quality (zombie prices, gaps) con retry automatico
- **Determinismo Assoluto**: Il ciclo "produce → esegue → contabilizza" è completamente deterministico
- **Reject Logging**: Ogni trade rifiutato loggato con motivazione (cash_reserve, max_positions, overlap)
- **Audit Trail Completo**: orders_plan con decision_path, reason_code, candidate_score, reject_reason
- **Closed Loop**: Sistema completo da segnali a ledger con controlli robusti
- **Decision support / simulazione backtest-grade**: segnali, ordini proposti (dry-run), controlli rischio, contabilità fiscale simulata e report riproducibili
- **Non è execution automatica**: sistema è *human-in-the-loop* (manual gate) per decisioni finali
- **Gap Production**: Manca execution bridge broker reale, monitoring/alerting, disaster recovery automatico
- **Stato Reale**: Robusto per backtest e decision support, non ancora autonomous production

---

## 2) Setup (Windows)

Prerequisiti:
- Python Launcher `py`
- (opzionale) Git

Installazione:
```powershell
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install -r requirements.txt
```

Inizializzazione DB:
```powershell
py scripts/setup/setup_db.py
py scripts/setup/load_trading_calendar.py
```

---

## 3) Flusso operativo EOD (EntryPoints)

Nota baseline **EUR/ACC**: strumenti non-EUR o a distribuzione (DIST) sono **bloccati** salvo feature flag esplicito.

### EP-03 — Ingestion (staging + quality gates)
```powershell
py scripts/data/ingest_data.py
```

### EP-04 — Health Check (gap/zombie) + Risk Continuity se necessario
```powershell
py scripts/quality/health_check.py
```

### EP-05 — Compute Signals
```powershell
py scripts/data/compute_signals.py
```

Modalità avanzate (periodi critici / rolling / full storico):

```powershell
# FULL storico (usa min/max disponibili per ogni simbolo)
py scripts/data/compute_signals.py --preset full

# RECENT mobile (rolling window; default 365 giorni)
py scripts/data/compute_signals.py --preset recent --recent-days 365

# Periodi critici (preset)
py scripts/data/compute_signals.py --preset gfc
py scripts/data/compute_signals.py --preset eurocrisis
py scripts/data/compute_signals.py --preset covid
py scripts/data/compute_signals.py --preset inflation2022

# Range custom
py scripts/data/compute_signals.py --start-date 2020-02-01 --end-date 2020-06-30

# ALL (full + recent + periodi critici)
py scripts/data/compute_signals.py --all --recent-days 365
```

### EP-06 — Check Guardrails
```powershell
py scripts/risk/check_guardrails.py
```

### EP-07 — Strategy Engine (dry-run / commit)
```powershell
# Dry-run (solo generazione ordini)
py scripts/trading/strategy_engine.py --dry-run

# Commit (esegue ordini automaticamente)
py scripts/trading/strategy_engine.py --commit
```
Output: `data/reports/<run_id>/orders.json` con:
- ordini proposti (BUY/SELL/HOLD) e motivazioni (`explain_code`)
- stime costi/attrito (`fees_est`, `tax_friction_est`, `momentum_score`)
- **`trade_score`** + **`recommendation`** (HOLD/TRADE)

Nota output file:
- file JSON diff-friendly salvato in `data/orders/orders_<timestamp>.json`
- copia anche nella sessione corrente `data/reports/sessions/<timestamp>/06_strategy/`

### EP-08 — Execute Orders (bridge)
```powershell
py scripts/trading/execute_orders.py --commit
```
Output: `fiscal_ledger` + `trade_journal` con contabilizzazione fiscale completa.

### EP-09 — Update Ledger (cash interest + sanity)
```powershell
py scripts/trading/update_ledger.py --commit
```

### EP-10 — Complete Cycle (orchestration)
```powershell
# Dry-run completo
py scripts/orchestration/run_complete_cycle.py --dry-run

# Esecuzione completa
py scripts/orchestration/run_complete_cycle.py --commit
```

### EP-15 — Backtest Runner
```powershell
py scripts/backtest/backtest_runner.py
```
Output: Run Package completo con simulazione realistica.

Modalità avanzate (coerenti con EP-05):

```powershell
# FULL storico (usa min/max disponibili per i segnali)
py scripts/backtest/backtest_runner.py --preset full

# RECENT mobile (rolling window; default 365 giorni)
py scripts/backtest/backtest_runner.py --preset recent --recent-days 365

# Periodi critici (preset)
py scripts/backtest/backtest_runner.py --preset gfc
py scripts/backtest/backtest_runner.py --preset eurocrisis
py scripts/backtest/backtest_runner.py --preset covid
py scripts/backtest/backtest_runner.py --preset inflation2022

# Range custom
py scripts/backtest/backtest_runner.py --start-date 2020-02-01 --end-date 2020-06-30

# ALL (full + recent + periodi critici)
py scripts/backtest/backtest_runner.py --all --recent-days 365
```

### EP-12 — Portfolio Risk Monitor (VaR/CVaR)
```powershell
py scripts/reports/portfolio_risk_monitor.py
```
**Obiettivo:** Monitoring operativo del rischio portfolio corrente
- Simulazione forward-looking con Geometric Brownian Motion
- Metriche: VaR 95%, CVaR 95%, distribuzione valore futuro
- Use case: Risk management giornaliero, posizioni attuali

### EP-13 — Sanity Check (bloccante)
```powershell
py scripts/quality/sanity_check.py
```

### EP-14 — Performance Report
```powershell
py scripts/reports/performance_report_generator.py
```

### EP-17 — Monte Carlo Stress Test (Gate Finale Pre-AUM)
```powershell
# Modalità synthetic (dati generati per test)
py scripts/analysis/monte_carlo_stress_test.py --n-sims 1000 --seed 42

# Modalità real (dati da fiscal_ledger)
py scripts/analysis/monte_carlo_stress_test.py --start-date 2023-01-01 --n-sims 1000

# Con runner helper
py scripts/analysis/monte_carlo_run_example.py --mode synthetic --n-days 504 --n-sims 1000
```
**Obiettivo:** Validazione robustezza strategia (gate DIPF §9.3)
- Shuffle test su returns storici (permutazioni casuali)
- Metriche: Distribuzione CAGR/MaxDD, Sharpe, Sortino, Calmar
- Use case: Gate finale pre-AUM, validazione strategia

**Output:** 
- Report JSON: `data/reports/sessions/<timestamp>/stress_tests/monte_carlo_stress_test_<timestamp>.json`
- Report Markdown con tabelle distribuzione e worst/best case
- Exit code: 0 se gate passed (5th percentile MaxDD < 25%), 1 se failed

**Gate Criteria (DIPF §9.3):**
- ✅ 5th percentile MaxDD < 25% (retail risk tolerance)
- ✅ Analisi distribuzione su 1000 simulazioni shuffle test
- ✅ Worst/best case scenarios identificati
- ✅ Riproducibilità garantita (seed fisso)

---

## 4) Run Package e Reports

### Struttura Reports
```
data/reports/sessions/<timestamp>/
├── 01_health_checks/
├── 02_automated/
├── 03_guardrails/
├── 04_risk/
├── 05_stress_tests/
├── 06_strategy/
├── 07_backtests/
├── 08_performance/
├── 09_analysis/
└── session_info.json
```

### Run Package Files
- `manifest.json` - Metadata esecuzione
- `kpi.json` - KPI performance
- `summary.md` - Report riassuntivo
- `orders.json` - Ordini proposti

**🚀 Comandi Report:**
```powershell
# Health check completo
py scripts/quality/health_check.py
# Output: data/reports/sessions/<timestamp>/01_health_checks/health_checks_<timestamp>.md

# Portfolio risk monitor (VaR/CVaR)
py scripts/reports/portfolio_risk_monitor.py
# Output: data/reports/sessions/<timestamp>/05_stress_tests/stress_test_<timestamp>.json

# Monte Carlo stress test (gate finale)
py scripts/analysis/monte_carlo_stress_test.py --start-date 2023-01-01
# Output: data/reports/sessions/<timestamp>/stress_tests/monte_carlo_stress_test_<timestamp>.json

# Report performance completo
py scripts/reports/performance_report_generator.py
# Analizza tutti i report disponibili
```

**🎯 Accesso Rapido:**
```powershell
# Session corrente con dati reali
Get-Content data/reports/sessions/<timestamp>/session_info.json

# Report stress test
Get-Content data/reports/sessions/<timestamp>/05_stress_tests/stress_test_*.json

# Report performance
Get-Content data/reports/sessions/<timestamp>/08_performance/performance_*.json
```

---

## 5) Scripts Organization

### Struttura Pulita
```
scripts/
├── core/           # Moduli production (17 file)
├── utility/        # Manutenzione dati (2 file)
├── archive/        # File obsoleti (0 file)
└── temp/           # File temporanei da pulire
```

### Core Scripts (Production)
- `setup_db.py` - Database setup
- `load_trading_calendar.py` - Trading calendar
- `ingest_data.py` - Data ingestion
- `health_check.py` - Health monitoring
- `compute_signals.py` - Signal generation
- `check_guardrails.py` - Risk guardrails
- `strategy_engine.py` - Strategy execution
- `execute_orders.py` - Order execution
- `update_ledger.py` - Ledger updates
- `run_complete_cycle.py` - Complete orchestration
- `backtest_engine.py` - Backtesting simulation
- `portfolio_risk_monitor.py` - Portfolio risk monitoring (VaR/CVaR)
- `monte_carlo_stress_test.py` - Monte Carlo gate (DIPF §9.3)
- `sanity_check.py` - Sanity validation
- `performance_report_generator.py` - Performance reports
- `enhanced_risk_management.py` - Advanced risk controls
- `trailing_stop_v2.py` - Trailing stop implementation
- `schema_contract_gate.py` - Schema validation

### Utility Scripts
- `data_quality_audit.py` - Data quality validation
- `extend_historical_data.py` - Historical data extension

---

## 6) Troubleshooting & Best Practices

### Issues Comuni
- **"Schema non conforme"**: Eseguire `py tests/test_schema_validation.py`
- **"Cash insufficiente"**: Verificare pre-trade controls in `execute_orders.py`
- **"Zombie prices"**: Controllare `scripts/quality/zombie_exclusion_enforcer.py`
- **"Volatilità elevata"**: Review `scripts/risk/enhanced_risk_management.py`

### Best Practices
1. **Sempre dry-run prima di commit**
2. **Verificare health_check dopo ingestione**
3. **Controllare guardrails prima di eseguire**
4. **Backup DB prima di commit importanti**
5. **Monitorare session_info.json per metadata**

---

## 7) Documenti Canonici

Per design e approfondimenti:
- **AGENT_RULES** - Regole operative per sviluppatori
- **PROJECT_OVERVIEW** - Visione e architettura sistema
- **DIPF** - Design framework completo
- **DATADICTIONARY** - Schema dati e strutture
- **TODOLIST** - Piano implementazione

---

## 8) Baseline EUR/ACC

**Configurazione produzione:**
- Universe: Solo ETF EUR/ACC
- Fiscalità: OICR_ETF (tassazione 26%)
- Execution: T+1_OPEN (default)
- Cost Model: TER drag + slippage dinamico
- Risk Management: Enhanced con volatility controls

**Feature flags (disabilitate):**
- FX trading (non-EUR)
- Distribution policy (DIST)
- Cash-equivalent parking

---

**Sistema pronto per backtest e decision support con semaforica coordinata.**
