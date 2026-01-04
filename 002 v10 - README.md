# 🇪🇺 ETF_ITA — Smart Retail (README)

| Meta-Dato | Valore |
| :--- | :--- |
| **Package (canonico)** | v10 |
| **Doc Revision (internal)** | r25 — 2026-01-04 |
| **Baseline Produzione** | **EUR / ACC** (solo ETF UCITS ad accumulazione in EUR) |
| **Stato Sistema** | **COMPLETATO** (10/10 EntryPoint) |
| **Performance Sharpe** | **0.96** (ottimizzato) |
| **Issues Integrity** | **75** (85.3% weekend/festivi) |

---

## 1) Descrizione del sistema

Sistema EOD per gestione portafoglio ETF "risk-first" per residenti italiani, con:
- data quality gating (staging → master)
- guardrails + sizing
- ledger fiscale (PMC) + journaling (forecast/postcast)
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

## 4) Run Package (reporting serializzato)

Percorso: `data/reports/<run_id>/`

Artefatti obbligatori:
- `manifest.json` (config_hash + data_fingerprint)
- `kpi.json` (kpi_hash)
- `summary.md` (include sezione Emotional Gap)

Se manca un file obbligatorio: la run è **FAIL** (exit code ≠ 0).

---

## 5) Regole chiave (baseline)

- **Segnali** su `adj_close`, **ledger/valorizzazione** su `close`.
- **Zombie prices**: esclusi dai KPI di rischio.
- **Benchmark**: se `benchmark_kind=INDEX` → no tasse simulate (solo friction proxy); se ETF → tassazione simulata coerente.
- **EUR/ACC gate**: blocco strumenti non conformi salvo feature flag.

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

## 7) Utility scripts (opzionali)

### 🔍 Utility Scripts
```powershell
py scripts/utility/analyze_warning.py          # Analisi integrity issues EP-04
py scripts/utility/check_issues.py              # Check dettagliato health issues
py scripts/utility/clear_signals.py             # Pulizia tabella signals
py scripts/utility/final_system_status.py      # Report completo stato sistema
py scripts/utility/performance_report_generator.py # Report performance completo
```

### 📊 Performance Reports
```powershell
# Report disponibili in data/reports/analysis/
py scripts/core/performance_report_generator.py     # Genera report completo
py scripts/core/health_check.py                        # Health check sistema
py scripts/core/stress_test.py                            # Monte Carlo stress test
py scripts/core/automated_test_cycle.py                   # Analisi ottimizzazione
```

**📁 Report Location:**
```
data/reports/analysis/
├── health_report_20260104_164700.md      # Health check completo
├── stress_test_20260104_172824.json       # Monte Carlo stress test
├── automated_test_cycle_20260104_173315.json # Analisi ottimizzazione
└── README.md                              # Guida reports
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
