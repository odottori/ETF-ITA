# 🇪🇺 ETF_ITA — Smart Retail (README)

| Meta-Dato | Valore |
| :--- | :--- |
| **Package (canonico)** | v10 |
| **Doc Revision (internal)** | r23 — 2026-01-04 |
| **Baseline Produzione** | **EUR / ACC** (solo ETF UCITS ad accumulazione in EUR) |
| **Stato Sistema** | **COMPLETATO** (10/10 EntryPoint) |
| **Performance Sharpe** | **0.96** (ottimizzato) |
| **Issues Integrity** | **75** (85.3% weekend/festivi) |

---

## 1) Mission

Sistema EOD per gestione portafoglio ETF "risk-first" per residenti italiani, con:
- data quality gating (staging → master)
- guardrails + sizing
- ledger fiscale (PMC) + journaling (forecast/postcast)
- reporting serializzato (Run Package)

## 1.1) Scopo del progetto
- **Decision support / simulazione backtest-grade**: genera segnali, ordini proposti (dry-run), controlli di rischio, contabilità fiscale simulata e reporting riproducibile.
- **Non è un sistema di execution automatica**: l’operatività reale richiede revisione e conferma esplicite (manual gate), soprattutto in presenza di guardrails/circuit breaker.

---

## 2) Setup (Windows)

Prerequisiti:
- Python Launcher `py`
- (consigliato) Git

Installazione:
```powershell
py -m venv .venv
.\.venv\Scriptsctivate
py -m pip install -r requirements.txt
```

---

## 3) Stato Attuale Sistema (2026-01-04)

### ✅ **SISTEMA COMPLETAMENTE IMPLEMENTATO**
- **10/10 EntryPoint** completati e testati
- **90% success rate** nei test di sistema
- **0 Failed** - **0 Errors**
- **1 Warning** (integrity issues minori)

### 🤖 **OTTIMIZZAZIONE AUTOMATICA COMPLETATA**
- **Sharpe Ratio**: 0.96 (eccellente)
- **Strategy CAGR**: 11.78%
- **Benchmark CAGR**: 17.65%
- **Alpha**: -5.87%
- **Configurazione salvata**: `optimal_strategy_20260104_172202.json`

### 🔍 **DATA QUALITY**
- **Records totali**: 10,898
- **Periodo**: 2010-2026 (16+ anni)
- **Integrity issues**: 75 (85.3% weekend/festivi)
- **Zombie prices**: 0 (completamente risolti)

### 🔧 **COMPONENTI ROBUSTI**
- **Database**: 10 tabelle complete
- **Signal Engine**: 120 segnali funzionanti
- **Risk Management**: Guardrails attivi
- **Fiscal Ledger**: 3 transazioni
- **Trading Calendar**: 2,192 giorni configurati

---

## 4) Flusso Operativo EOD (EntryPoints)

Nota operativa: per baseline **EUR/ACC**, strumenti non-EUR o DIST sono **bloccati** con messaggio esplicativo.

### EP-01 — Setup DB
```powershell
py scripts/setup_db.py
```

### EP-02 — Carica Trading Calendar
```powershell
py scripts/load_trading_calendar.py
```

### EP-03 — Ingestion (staging + quality gates)
```powershell
py scripts/ingest_data.py
```

### EP-04 — Health Check (zombie/gap) + Risk Continuity se necessario
```powershell
py scripts/health_check.py
```

### EP-05 — Compute Signals
```powershell
py scripts/compute_signals.py
```

### EP-06 — Check Guardrails
```powershell
py scripts/check_guardrails.py
```

### EP-07 — Strategy Engine (dry-run)
```powershell
py scripts/strategy_engine.py --dry-run
```
Output: `data/reports/<run_id>/orders.json` con HOLD/TRADE e `do_nothing_score`.

### EP-08 — Update Ledger (commit)
```powershell
py scripts/update_ledger.py --commit
```
Best practice: eseguire backup prima del commit.

### EP-09 — Backtest Runner (Run Package)
```powershell
py scripts/backtest_runner.py
```
Produce: `manifest.json`, `kpi.json`, `summary.md`.

### EP-10 — Stress Test (Monte Carlo)
```powershell
py scripts/stress_test.py
```

### EP-11 — Sanity Check (bloccante)
```powershell
py scripts/sanity_check.py
```

### 🤖 Ottimizzazione Automatica Strategie
```powershell
py scripts/auto_strategy_optimizer.py
```
Output: `data/reports/optimal_strategy_*.json` con configurazione ottimale

### 🔍 Test Completo Sistema
```powershell
py scripts/complete_system_test.py
```
Output: `data/reports/system_test_*.json` con assessment completo

### 🔍 Utility Scripts
```powershell
py scripts/utility/analyze_warning.py          # Analisi integrity issues EP-04
py scripts/utility/check_issues.py              # Check dettagliato health issues
py scripts/utility/clear_signals.py             # Pulizia tabella signals
py scripts/utility/final_system_status.py      # Report completo stato sistema
py scripts/utility/performance_report_generator.py # Report performance completo
```

### 📁 Scripts Organization
```
scripts/
├── core/           # Core system scripts (EP-01..EP-10)
├── utility/        # Analysis, testing, and utility scripts
├── archive/        # Temporary implementation scripts
└── advanced/       # Advanced ML and optimization scripts
```

---

## 5) Run Package (serializzato)

Percorso: `data/reports/<run_id>/`

Obbligatori:
- `manifest.json` (config_hash + data_fingerprint)
- `kpi.json` (kpi_hash)
- `summary.md` (include Emotional Gap)

Se manca un file obbligatorio: la run è **FAIL**.

---

## 5) Regole chiave (da ricordare)
- Segnali su `adj_close`, valorizzazione ledger su `close`.
- Zombie prices: esclusi dai KPI rischio.
- Benchmark: se INDEX → no tasse simulate; se ETF → tasse simulate.
- Baseline EUR/ACC: blocco strumenti non conformi.

---

## 6) Struttura progetto
```
ETF_ITA_project/
├── config/
│   └── etf_universe.json
├── data/
│   ├── etf_data.duckdb
│   └── reports/
├── docs/
│   ├── 002 v10 - DIPF ETF-ITA prj.md
│   ├── 002 v10 - DATADICTIONARY.md
│   └── 002 v10 - TODOLIST.md
└── scripts/
    ├── setup_db.py
    ├── load_trading_calendar.py
    ├── ingest_data.py
    ├── health_check.py
    ├── compute_signals.py
    ├── check_guardrails.py
    ├── strategy_engine.py
    ├── update_ledger.py
    ├── backtest_runner.py
    └── sanity_check.py
```

---

## 7) Nota importante

Questo progetto è *decision support / simulazione backtest-grade*. Non sostituisce il commercialista né costituisce consulenza finanziaria.
