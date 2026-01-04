# 🇪🇺 ETF_ITA — Smart Retail (README)

| Meta-Dato | Valore |
| :--- | :--- |
| **Package (canonico)** | v10 |
| **Doc Revision (internal)** | r24 — 2026-01-04 |
| **Baseline Produzione** | **EUR / ACC** (solo ETF UCITS ad accumulazione in EUR) |

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

Questi script non sono parte del “percorso operativo” standard, ma aiutano debug e manutenzione.

- `scripts/analyze_warning.py` — Analisi integrity issues EP-04 (zombie prices, gaps)
- `scripts/check_issues.py` — Check dettagliato health issues con reporting
- `scripts/clear_signals.py` — Pulizia tabella signals per reset
- `scripts/final_system_status.py` — Report completo stato sistema
- `scripts/performance_report_generator.py` — Report performance completo

---

## 8) Nota importante

Questo progetto è *decision support / simulazione backtest-grade*. Non sostituisce il commercialista né costituisce consulenza finanziaria.
