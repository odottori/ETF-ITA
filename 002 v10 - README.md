# 🇪🇺 ETF ITALIA PROJECT - Smart Retail (README)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r19 — 2026-01-04  

---

## 🎯 Mission
Sistema “smart retail” per residenti italiani: gestione portafoglio, simulazione/backtest, fiscalità e controllo rischio, con journaling Forecast/Postcast per misurare la qualità decisionale.

Documenti canonici:
- DIPF: requisiti e architettura
- DATADICTIONARY: contratto dati
- TODOLIST: piano implementativo
- README: operatività e comandi

---

## ⚠️ Disclaimer
Questo progetto fornisce stime e simulazioni; non sostituisce un consulente fiscale o l’intermediario. Le regole fiscali possono variare per strumento, regime e intermediario.

---

## 🧰 Prerequisiti
- Windows 10/11
- Python 3.10+ (Python Launcher `py`)
- Virtualenv consigliato

---

## 🛠️ Installazione
```powershell
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install -U pip
py -m pip install duckdb pandas yfinance plotly
```

---

## 📁 Struttura cartelle (minima)
```
ETF_ITA_project/
├── config/
│   └── etf_universe.json
├── data/
│   ├── etf_data.duckdb
│   ├── backup/
│   └── reports/
├── scripts/
└── strategies/
```

---

## ⚙️ Config (principi)
Il file `config/etf_universe.json` deve includere per ogni simbolo:
- `currency`, `dist_policy` (ACC/DIST), `tax_category` (OICR_ETF / ETC_ETN_STOCK)
- cost model (commissioni, slippage)
- execution model (default T+1_OPEN)
- `fx_enabled` + coppie necessarie (solo se strumenti non-EUR)

---

## 🚀 EntryPoints (1:1 con TODOLIST)

### EP-01 — Setup DB
```powershell
py scripts/setup_db.py
```

### EP-02 — Load Trading Calendar
```powershell
py scripts/load_trading_calendar.py --venue BIT --csv config/trading_calendar_BIT.csv
```

### EP-03 — Ingestione dati (EOD)
```powershell
py scripts/ingest_data.py
```
Output: `market_data` aggiornato + record `ingestion_audit`.

### EP-04 — Health Check (incl. zombie data)
```powershell
py scripts/health_check.py
```
Output: `data/health_report.md` (+ warning su buchi, zombie, mismatch).

### EP-05 — Compute Signals
```powershell
py scripts/compute_signals.py
```
Usa `strategies/alpha_signals.py`.

### EP-06 — Guardrails
```powershell
py scripts/check_guardrails.py
```
Output: SAFE/DANGER + motivazione.

### EP-07 — Pianificazione ordini (Dry-Run)
```powershell
py scripts/plan_orders.py --dry-run
```
Output: `data/orders.json` (nessuna scrittura su ledger).

### EP-08 — Update Ledger (solo con commit)
```powershell
py scripts/update_ledger.py          # dry-run
py scripts/update_ledger.py --commit # scrive su fiscal_ledger
```
**Prima del commit**: backup DB obbligatorio (automatico nello script).

### EP-09 — Backtest
```powershell
py scripts/run_backtest.py
```

### EP-10 — Generazione report + Run Package (obbligatorio)
```powershell
py scripts/generate_report.py
```
Output: `data/reports/<run_id>/` con:
- `manifest.json`
- `kpi.json`
- `summary.md`

### EP-11 — Stress test
```powershell
py scripts/stress_test.py --quick
```

### EP-12 — Restore DB
```powershell
py scripts/restore_db.py --from data/backup/etf_data.duckdb.backup
```

---

## 🧭 Flusso operativo consigliato (giornaliero)
1) EP-03 ingest  
2) EP-04 health check  
3) EP-05 signals  
4) EP-06 guardrails  
5) EP-07 dry-run ordini  
6) Review manuale se warning/breaker  
7) EP-08 commit (solo se deciso)  
8) EP-10 report (Run Package)

---

## 📄 Run Package: perché è obbligatorio
Ogni run deve essere riproducibile: parametri, dati, KPI e hash devono essere serializzati.  
Se manca un artefatto del Run Package, la run è invalida (exit code != 0).

---

## 🧠 Reporting “serio”: Emotional Gap
Nel `summary.md` viene calcolato (se journaling disponibile):
- PnL strategia pura (senza override)
- PnL strategia reale (con override)
Se il gap è negativo, il report deve evidenziarlo.

