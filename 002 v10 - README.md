# 🇪🇺 ETF ITALIA PROJECT - Smart Retail (README)

**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r22 — 2026-01-04  
**Baseline produzione:** **EUR / ACC** (universe bloccato su strumenti in EUR e ad accumulazione)

---

## 1. Scopo
Sistema “smart retail” per residenti italiani: ingestione dati EOD, calcolo segnali oggettivi, guardrails, simulazione/decision support, fiscalità (PMC, imposta 26%, zainetto *dove applicabile*), e reporting *riproducibile* tramite Run Package serializzato.

Documenti canonici:
- **DIPF**: requisiti e architettura end-to-end
- **DATADICTIONARY**: contratto dati (tabelle, viste, artefatti)
- **TODOLIST**: piano implementativo (DoD testabili)
- **README**: operatività e comandi

---

## 2. Baseline v10 (EUR/ACC) — cosa è attivo
Attivo “out of the box”:
- Universo strumenti **solo EUR** e **ACC** (niente multi-valuta, niente distribuzione cash).
- Prezzi: `adj_close` per segnali; `close` per valorizzazione ledger (vedi DIPF §2.1).
- Fiscalità: categoria fiscale di default `OICR_ETF` (gain tassato pieno, no compensazione zainetto nel modello).
- Benchmark: consigliato **ETF UCITS EUR/ACC**; se si usa un **indice** (es. `^GSPC`) è solo proxy e nel reporting non si applicano tasse simulate.
- Run Package obbligatorio per ogni run con KPI (manifest + KPI + summary).
- Sanity check bloccante e health check operativi.

Disattivato nel baseline (feature flag):
- FX (`fx_rates`, `exchange_rate_used`) — si abilita solo se si ammettono strumenti non-EUR.
- Dividendi cash (DIST) — si abilita solo se si ammettono strumenti a distribuzione.

---

## 3. Installazione (Windows)
Da PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install -U pip
py -m pip install duckdb pandas yfinance plotly matplotlib
```

---

## 4. EntryPoints (EP) — superficie eseguibile (1:1 con TODOLIST)
| EP | Comando | Output principale | Note |
|---|---|---|---|
| EP-01 | `py scripts/setup_db.py` | Crea `data/etf_data.duckdb` + schema | DD-2..DD-11 |
| EP-02 | `py scripts/load_trading_calendar.py` | Popola `trading_calendar` | DD-3.1 |
| EP-03 | `py scripts/ingest_data.py` | `market_data` + `ingestion_audit` | EOD |
| EP-04 | `py scripts/health_check.py` | `data/health_report.md` | zombie/stale/gap |
| EP-05 | `py scripts/compute_signals.py` | segnali + snapshot | strategies/ |
| EP-06 | `py scripts/check_guardrails.py` | SAFE/DANGER + motivazioni | dry-run gate |
| EP-07 | `py scripts/strategy_engine.py --dry-run` | `data/orders.json` | nessuna scrittura |
| EP-08 | `py scripts/update_ledger.py --commit` | scrive `fiscal_ledger` | include backup |
| EP-09 | `py scripts/backtest_runner.py` | Run Package completo | include sanity |
| EP-10 | `py scripts/stress_test.py` | stress report | finestre crisi |

---

## 5. Flusso operativo giornaliero (EOD)
1) **Ingestione**
Nota: l’ingestione applica una soglia di spike per simbolo (`max_daily_move_pct`, default 15%) e scarta movimenti anomali registrandoli nell’audit.
```powershell
py scripts/ingest_data.py
```

2) **Health check (obbligatorio)**
```powershell
py scripts/health_check.py
```
Se emergono warning hard (gap su giorni open, zombie prices, revisioni hard), fermarsi e correggere prima di procedere.

3) **Segnali + guardrails**
```powershell
py scripts/compute_signals.py
py scripts/check_guardrails.py
```

4) **Dry-run ordini (sempre)**
```powershell
py scripts/strategy_engine.py --dry-run
```
Output: `data/orders.json` (diff-friendly) con impatto su cash/tasse, stime costi, `do_nothing_score` e raccomandazione (HOLD/TRADE).

5) **Commit (solo se OK)**
```powershell
py scripts/update_ledger.py --commit
```
Requisiti: manual gate se breaker/warning hard; backup pre-commit automatico.

---

## 6. Run Package (report prestazionale serializzato)
Ogni run che produce KPI deve creare la cartella:
`data/reports/<run_id>/`

Artefatti minimi **obbligatori**:
- `manifest.json` (parametri, universe, cost model, tax model, `config_hash`, `data_fingerprint`)
- `kpi.json` (KPI + `kpi_hash`)
- `summary.md` (riassunto leggibile)

Se manca un artefatto obbligatorio → run invalida (exit code != 0).  
Schema minimo: vedi DD-11.

---

## 7. Reporting “serio”: Emotional Gap
Nel `summary.md` (se journaling disponibile) viene riportato l’**Emotional Gap**:
- PnL “Strategia Pura” (segnali automatici, no override)
- PnL “Strategia Reale” (eseguito, inclusi override)

Se gap < 0, il report evidenzia esplicitamente il costo degli interventi manuali.

---

## 8. Utility (non-EP ma consigliate)
- Backup manuale: `py scripts/backup_db.py`
- Restore: `py scripts/restore_db.py --from <path_backup>`
- CHECKPOINT / maintenance: eseguito in `backup_db.py` o `health_check.py` come step periodico (vedi DIPF §8.2)

---

## 9. Nota importante
Questo progetto è *decision support / simulazione backtest-grade*. Non sostituisce il commercialista né costituisce consulenza finanziaria.
