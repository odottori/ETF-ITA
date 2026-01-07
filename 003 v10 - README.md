# 🇪🇺 ETF_ITA — Smart Retail (README)

| Meta-Dato | Valore |
| :--- | :--- |
| **Package (canonico)** | v10.8 |
| **Doc Revision** | r38 — 2026-01-07 |
| **Baseline Produzione** | **EUR / ACC** (solo ETF UCITS ad accumulazione in EUR) |
| **Stato Sistema** | **PRODUCTION READY v10.8** |
| **Scripts Funzionanti** | **18/18** (100% success) |
| **Closed Loop** | **ROBUST MUTUAL EXCLUSION** (commit > dry-run, deterministic) |
| **Determinismo Ciclo** | **IMPLEMENTATO** (produce → esegue → contabilizza sempre deterministico) |
| **Backtest Engine** | **EVENT-DRIVEN** (day-by-day, SELL→BUY, cash management corretto) |
| **Auto-Update** | **PROATTIVO** (ingest + compute automatico, data freshness check) |
| **Market Calendar** | **INTELLIGENTE** (festività + auto-healing chiusure eccezionali) |
| **Strategy Engine** | **MOMENTUM SCORE IMPLEMENTED** (euristico 0-1, mandatory vs opportunistic) |
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
- **Determinismo Assoluto**: Il ciclo "produce → esegue → contibilizza" è completamente deterministico
- **Pre-Trade Hard Controls**: Cash e posizione verificati prima di ogni trade
- **Reject Logging**: Ogni trade rifiutato viene loggato con motivazione chiara
- **Mutua Exclusion**: Modalità --commit e --dry-run mutualmente esclusive
- **Closed Loop**: Sistema completo da segnali a ledger con controlli robusti
- **Decision support / simulazione backtest-grade**: segnali, ordini proposti (dry-run), controlli rischio, contabilità fiscale simulata e report riproducibili.
- **Non è execution automatica**: la produzione è *human-in-the-loop* (manual gate), soprattutto in caso di guardrails/circuit breaker.

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
py scripts/core/setup_db.py
py scripts/core/load_trading_calendar.py
```

---

## 3) Flusso operativo EOD (EntryPoints)

Nota baseline **EUR/ACC**: strumenti non-EUR o a distribuzione (DIST) sono **bloccati** salvo feature flag esplicito.

### EP-03 — Ingestion (staging + quality gates)
```powershell
py scripts/core/ingest_data.py
```

### EP-04 — Health Check (gap/zombie) + Risk Continuity se necessario
```powershell
py scripts/core/health_check.py
```

### EP-05 — Compute Signals
```powershell
py scripts/core/compute_signals.py
```

Modalità avanzate (periodi critici / rolling / full storico):

```powershell
# FULL storico (usa min/max disponibili per ogni simbolo)
py scripts/core/compute_signals.py --preset full

# RECENT mobile (rolling window; default 365 giorni)
py scripts/core/compute_signals.py --preset recent --recent-days 365

# Periodi critici (preset)
py scripts/core/compute_signals.py --preset gfc
py scripts/core/compute_signals.py --preset eurocrisis
py scripts/core/compute_signals.py --preset covid
py scripts/core/compute_signals.py --preset inflation2022

# Range custom
py scripts/core/compute_signals.py --start-date 2020-02-01 --end-date 2020-06-30

# ALL (full + recent + periodi critici)
py scripts/core/compute_signals.py --all --recent-days 365
```

### EP-06 — Check Guardrails
```powershell
py scripts/core/check_guardrails.py
```

### EP-07 — Strategy Engine (dry-run / commit)
```powershell
# Dry-run (solo generazione ordini)
py scripts/core/strategy_engine.py --dry-run

# Commit (esegue ordini automaticamente)
py scripts/core/strategy_engine.py --commit
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
py scripts/core/execute_orders.py --commit
```
Output: `fiscal_ledger` + `trade_journal` con contabilizzazione fiscale completa.

### EP-09 — Update Ledger (cash interest + sanity)
```powershell
py scripts/core/update_ledger.py --commit
```

### EP-10 — Complete Cycle (orchestration)
```powershell
# Dry-run completo
py scripts/core/run_complete_cycle.py --dry-run

# Esecuzione completa
py scripts/core/run_complete_cycle.py --commit
```

### EP-15 — Backtest Runner
```powershell
py scripts/core/backtest_runner.py
```
Output: Run Package completo con simulazione realistica.

Modalità avanzate (coerenti con EP-05):

```powershell
# FULL storico (usa min/max disponibili per i segnali)
py scripts/core/backtest_runner.py --preset full

# RECENT mobile (rolling window; default 365 giorni)
py scripts/core/backtest_runner.py --preset recent --recent-days 365

# Periodi critici (preset)
py scripts/core/backtest_runner.py --preset gfc
py scripts/core/backtest_runner.py --preset eurocrisis
py scripts/core/backtest_runner.py --preset covid
py scripts/core/backtest_runner.py --preset inflation2022

# Range custom
py scripts/core/backtest_runner.py --start-date 2020-02-01 --end-date 2020-06-30

# ALL (full + recent + periodi critici)
py scripts/core/backtest_runner.py --all --recent-days 365
```

### EP-12 — Stress Test
```powershell
py scripts/core/stress_test.py
```

### EP-13 — Sanity Check (bloccante)
```powershell
py scripts/core/sanity_check.py
```

### EP-14 — Performance Report
```powershell
py scripts/core/performance_report_generator.py
```

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
py scripts/core/health_check.py
# Output: data/reports/sessions/<timestamp>/01_health_checks/health_checks_<timestamp>.md

# Stress test Monte Carlo
py scripts/core/stress_test.py
# Output: data/reports/sessions/<timestamp>/05_stress_tests/stress_test_<timestamp>.json

# Report performance completo
py scripts/core/performance_report_generator.py
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
- `stress_test.py` - Stress testing
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
- **"Zombie prices"**: Controllare `scripts/core/zombie_exclusion_enforcer.py`
- **"Volatilità elevata"**: Review `scripts/core/enhanced_risk_management.py`

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
