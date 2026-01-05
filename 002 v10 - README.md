# 🇪🇺 ETF_ITA — Smart Retail (README)

| Meta-Dato | Valore |
| :--- | :--- |
| **Package (canonico)** | v10 |
| **Doc Revision (internal)** | r29 — 2026-01-05 |
| **Baseline Produzione** | **EUR / ACC** (solo ETF UCITS ad accumulazione in EUR) |

---

## 1) Descrizione del sistema

Sistema EOD per gestione portafoglio ETF "risk-first" per residenti italiani, con:
- data quality gating (staging → master)
- guardrails + sizing
- ledger fiscale (PMC) + journaling (forecast/postcast)
- **session management centralizzato** con prefissi ordinali
- reporting serializzato (Run Package)

### 1.1 Scopo
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
py scripts/setup_db.py
py scripts/load_trading_calendar.py
```

---

## 3) Flusso operativo EOD (EntryPoints)

Nota baseline **EUR/ACC**: strumenti non-EUR o a distribuzione (DIST) sono **bloccati** salvo feature flag esplicito.

### EP-03 — Ingestion (staging + quality gates)
```powershell
py scripts/ingest_data.py
```

### EP-04 — Health Check (gap/zombie) + Risk Continuity se necessario
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
Output: `data/reports/<run_id>/orders.json` con:
- ordini proposti (BUY/SELL/HOLD) e motivazioni (`explain_code`)
- stime costi/attrito (`fees_est`, `tax_friction_est`, `expected_alpha_est`)
- **`do_nothing_score`** + **`recommendation`** (HOLD/TRADE)

### EP-08 — Update Ledger (commit)
```powershell
py scripts/update_ledger.py --commit
```
Best practice: eseguire backup prima del commit.

### EP-09 — Backtest Runner (Run Package)
```powershell
py scripts/backtest_runner.py
```

### EP-11 — Sanity Check (bloccante)
```powershell
py scripts/sanity_check.py
```

---

## 4) Session Management & Semaforica

### 4.1 Session Manager Centralizzato

Il sistema usa un **Session Manager** che organizza tutti i report in sessioni timestampate:

```
data/reports/sessions/<YYYYMMDD_HHMMSS>/
├── 01_health_checks/     # Verifiche integrità sistema
├── 02_automated/         # Test automatici e cicli
├── 03_guardrails/        # Controlli risk management
├── 04_stress_tests/      # Test stress Monte Carlo
├── 05_strategy/          # Motore strategia e ordini
├── 06_backtests/         # Backtest completi
├── 07_performance/       # Metriche sistema
└── 08_analysis/          # Report riassuntivi
```

**Vantaggi:**
- ✅ **Ordinamento automatico** con prefissi ordinali
- ✅ **Tracciabilità completa** di ogni esecuzione
- ✅ **Nessun file sparso** in cartelle sbagliate
- ✅ **Sessioni TEST** leggere per controlli rapidi

### 4.2 Sessioni TEST

Per test estemporanei:
```python
from scripts.core.session_manager import get_test_session_manager
sm = get_test_session_manager()  # Crea sessione <timestamp>_TEST
```

Le sessioni TEST creano solo le cartelle essenziali (01, 03, 05, 08).

### 4.3 Semaforica Operativa

**🟢 VERDE** - Sistema operativo:
- Tutti i check passati
- Guardrails OK
- Ordini generabili

**🟡 GIALLO** - Attenzione:
- Warning presenti
- Guardrails borderline
- Revisione manuale richiesta

**🔴 ROSSO** - Sistema bloccato:
- Errori critici
- Guardrails violated
- Nessun ordine permesso

---

## 5) Run Package (reporting serializzato)

Percorso: `data/reports/sessions/<YYYYMMDD_HHMMSS>/06_backtests/`

Artefatti obbligatori con timestamp:
- `manifest_<timestamp>.json` (config_hash + data_fingerprint)
- `kpi_<timestamp>.json` (kpi_hash)
- `summary_<timestamp>.md` (include sezione Emotional Gap)

Se manca un file obbligatorio: la run è **FAIL** (exit code ≠ 0).

---

## 6) Quick Test (controlli rapidi)

Per test estemporanei del sistema:

```powershell
py scripts/core/quick_test.py
```

Crea una sessione TEST leggera con solo le cartelle essenziali:
- 01_health_checks/ - Verifiche base
- 03_guardrails/ - Controlli rischio
- 05_strategy/ - Motore strategia
- 08_analysis/ - Report finale

Ideale per:
- ✅ Verifiche pre-produzione
- ✅ Debug rapido
- ✅ Test di integrità
- ✅ Sviluppo iterativo

---

## 7) Regole chiave (baseline)

- **Segnali** su `adj_close`, **ledger/valorizzazione** su `close`.
- **Zombie prices**: esclusi dai KPI di rischio.
- **Benchmark**: se `benchmark_kind=INDEX` → no tasse simulate (solo friction proxy); se ETF → tassazione simulata coerente.
- **EUR/ACC gate**: blocco strumenti non conformi salvo feature flag.

---

## 8) Struttura progetto

```
ETF_ITA_project/
├── config/
│   └── etf_universe.json
├── data/
│   ├── etf_data.duckdb
│   └── reports/
│       └── sessions/           # Session management
│           ├── 20260105_160036/  # Sessione completa
│           │   ├── 01_health_checks/
│           │   ├── 02_automated/
│           │   ├── 03_guardrails/
│           │   ├── 04_stress_tests/
│           │   ├── 05_strategy/
│           │   ├── 06_backtests/
│           │   ├── 07_performance/
│           │   └── 08_analysis/
│           └── 20260105_160450_TEST/  # Sessione TEST
│               ├── 01_health_checks/
│               ├── 03_guardrails/
│               ├── 05_strategy/
│               └── 08_analysis/
├── scripts/
│   ├── core/                   # Session manager & test
│   │   ├── session_manager.py
│   │   ├── quick_test.py
│   │   ├── health_check.py
│   │   ├── check_guardrails.py
│   │   ├── stress_test.py
│   │   ├── strategy_engine.py
│   │   └── backtest_runner.py
│   ├── setup_db.py
│   ├── load_trading_calendar.py
│   ├── ingest_data.py
│   ├── compute_signals.py
│   └── update_ledger.py
└── docs/
    ├── 002 v10 - DIPF ETF-ITA prj.md
    ├── 002 v10 - DATADICTIONARY.md
    ├── 002 v10 - README.md
    └── 002 v10 - TODOLIST.md
```

---

## 7) Utility scripts (opzionali)

### 🔍 Utility Scripts
```powershell
py scripts/utility/analyze_warning.py          # Analisi integrity issues EP-04
py scripts/utility/check_issues.py              # Check dettagliato health issues
py scripts/utility/clear_signals.py             # Pulizia tabella signals
py scripts/utility/final_system_status.py      # Report completo stato sistema
py scripts/utility/performance_report_generator.py # Report performance completo
```

### 🔍 Risk Analysis Reports

**📁 Risk Analysis Structure:**
```
analysis/
├── scripts/
│   └── comprehensive_risk_analysis.py  # Analisi rischio completa
└── reports/
    ├── comprehensive_risk_analysis_20260105_091552.json  # Dati completi
    └── risk_assessment_summary.md  # Sintesi esecutiva
```

**🎯 Risk Analysis Results:**
- **Risk Level:** HIGH (Score: 0.530)
- **Correlazione CSSPX-XS2L:** 0.821 (molto alta)
- **Volatilità Portfolio:** 26.75% (elevata)
- **Max Drawdown:** -59.06% (critico)
- **Sharpe Ratio:** 0.924

**🚀 Comandi Risk Analysis:**
```powershell
# Analisi rischio completa
py analysis/scripts/comprehensive_risk_analysis.py
# Output: analysis/reports/comprehensive_risk_analysis_<timestamp>.json

# Report sintesi
# Output: analysis/reports/risk_assessment_summary.md
```

**🎯 Accesso Rapido Risk Analysis:**
```powershell
# Report completo rischio
Get-Content analysis/reports/comprehensive_risk_analysis_20260105_091552.json

# Sintesi esecutiva
Get-Content analysis/reports/risk_assessment_summary.md
```

### 📊 Performance Reports

**📁 Struttura Reports:**
```
data/reports/sessions/
└── 20260105_085740/           # Session con dati reali
    ├── automated/             # Report generati automaticamente
    │   ├── automated_test_cycle.json
    │   ├── health_check.json
    │   └── stress_test.json
    ├── analysis/               # Report analisi ad-hoc
    │   ├── complete_analysis.json
    │   └── project_analysis_report.md
    └── session_info.json      # Metadata sessione
```

**🎯 Logica di Organizzazione:**
- **Una sessione = un timestamp**: Tutti i report dello stesso periodo insieme
- **Sottocartelle per tipo**: automated/ vs analysis/ per separazione logica
- **Nomi file senza timestamp**: Solo tipo report (timestamp nella directory)
- **Formati uniformi**: JSON per dati, MD per report leggibili
- **Metadata centralizzati**: session_info.json per ogni sessione

**📋 Session Disponibile:**
- **20260105_085740**: Dati reali e analisi complete
  - **automated/**: Test cycle automatico
  - **analysis/**: Analisi progetto complete
  - **session_info.json**: Metadata sessione

**🚀 Comandi Report:**
```powershell
# Health check completo
py scripts/core/health_check.py
# Output: data/reports/sessions/<timestamp>/automated/health_check.json

# Stress test Monte Carlo
py scripts/core/stress_test.py
# Output: data/reports/sessions/<timestamp>/automated/stress_test.json

# Analisi ottimizzazione
py scripts/core/automated_test_cycle.py
# Output: data/reports/sessions/<timestamp>/automated/automated_test_cycle.json

# Report performance completo
py scripts/core/performance_report_generator.py
# Analizza tutti i report disponibili
```

**🎯 Accesso Rapido:**
```powershell
# Session corrente con dati reali
Get-Content data/reports/sessions/20260105_085740/session_info.json

# Report automatici
Get-Content data/reports/sessions/20260105_085740/automated/automated_test_cycle.json

# Report analisi
Get-Content data/reports/sessions/20260105_085740/analysis/complete_analysis.json

# Report leggibili
Get-Content data/reports/sessions/20260105_085740/analysis/project_analysis_report.md
```

### 📁 Scripts Organization
```
scripts/
├── core/           # Core system scripts (EP-01..EP-10)
├── utility/        # Analysis, testing, and utility scripts
├── archive/        # Temporary implementation scripts
└── advanced/       # [DELETED] Advanced ML and optimization scripts
```

### 🗑️ Advanced Scripts - ARCHIVIATI
Tutti gli advanced scripts sono stati archiviati perché:
- **Over-engineering**: ML non necessario per sistema semplice
- **Duplicazione**: Funzionalità già presenti in core scripts
- **Complessità**: Manutenzione troppo alta per valore aggiunto
- **Dependencies**: sklearn non necessario per produzione

**Scripts archiviati:**
- `adaptive_signal_engine.py` (436 linee) - ML signal engine
- `auto_strategy_optimizer.py` (451 linee) - ML optimizer
- `simple_strategy_optimizer.py` (337 linee) - Simple optimizer
- `master_runner.py` (400 linee) - Orchestrator
- `complete_system_test.py` (395 linee) - System test

**Vedi `scripts/advanced_analysis.md` per analisi dettagliata.**

---

## 8) Nota importante

Questo progetto è *decision support / simulazione backtest-grade*. Non sostituisce il commercialista né costituisce consulenza finanziaria.
