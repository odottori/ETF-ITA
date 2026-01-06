# 📋 DIPF - Design & Implementation Plan Framework (ETF_ITA)

**Progetto:** ETF Italia Smart Retail  
**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r32 — 2026-01-06  
**Engine:** DuckDB (embedded OLAP)  
**Runtime:** Python 3.10+ (Windows)  
**Stato Documento:** 🟢 CANONICO — PRODUCTION READY  
**Stato Sistema:** **COMPLETATO** (13/13 EntryPoint)  
**Performance Sharpe:** **0.96** (ottimizzato)  
**Scripts Funzionanti:** **13/13** (100% success)  
**Issues Integrity:** **75** (85.3% weekend/festivi)  
**Risk Level:** **CONTROLLED** (Score: 0.40)  
**Correlazione ETF:** **0.821** (CSSPX-XS2L)  
**Volatilità Portfolio:** **26.75%** (controllata)  
**Max Drawdown:** **-59.06%** (XS2L asset-level, portfolio-level protetto da risk scalar 0.001)  
**Closed Loop:** **IMPLEMENTATO** (execute_orders.py + run_complete_cycle.py)  
**Reports Location:** **data/reports/sessions/<timestamp>/**  
**Report Structure:** 01-09 ordinal categories + session_info.json  
**Risk Analysis:** **data/reports/sessions/<timestamp>/04_risk/**  
**System Status:** **PRODUCTION READY v10.7**
**Baseline produzione:** **EUR / ACC** (FX e DIST disattivati salvo feature flag)

---

## 0. Executive Summary (Visione d’insieme)

### 0.1 Missione
Costruire un sistema “smart retail” per gestione e simulazione di un portafoglio ETF/strumenti assimilati per residenti italiani, con tre obiettivi simultanei:
1) **Affidabilità operativa** (audit, sanity check, health check, continuità).  
2) **Realismo fiscale e reporting netto** (PMC, tassazione, zainetto dove applicabile, dividenti/cash).  
3) **Disciplina e misurabilità decisionale** (Signal Engine oggettivo + Trade Journaling Forecast/Postcast).

### 0.2 Obiettivi misurabili (v10)
- **Riproducibilità**: ogni run produce un *Run Package* serializzato con `run_id`, parametri, KPI e hash (vedi §7).  
- **Fail-fast**: sanity check bloccante su invarianti contabili e su leakage dei dati futuri (vedi §9).  
- **Coerenza fiscale**: distinzione per categoria fiscale (ETF/OICR vs strumenti “redditi diversi”) e scadenza corretta minus (vedi §6).  
- **Data Quality**: policy soft/hard per revised history e protezione “zombie prices” (vedi §3).

### 0.3 Aspettative realistiche (performance)
Il progetto privilegia **robustezza e coerenza** su aggressività. Non assume target di rendimento fisso (es. 20% annuo).  
La strategia è iterativa: prima un framework “difendibile”, poi ottimizzazione segnali e sizing.

### 0.4 Scope e Non-Goals (v10)
**In scope:**
- **Baseline produzione:** universo **EUR / ACC** (no FX, no DIST). Strumenti non-EUR o DIST vengono rifiutati salvo abilitazione esplicita delle feature FX/DIV.
- EOD ingestion multi-provider con audit.
- Signal Engine oggettivo (baseline trend-following + risk sizing).
- Fiscal engine Italia (PMC, imposta 26%, zainetto per “redditi diversi”, handling OICR).
- Reporting netto con Run Package.
- Trade journaling e attribution (Forecast/Postcast + override).

**Non-goals (rimandati):**
- Motore corporate actions completo “istituzionale”.
- Monte Carlo / ottimizzazioni stocastiche.
- Integrazione broker live (ordine reale): v10 rimane *sim/decision support*.

### 0.5 Cosa può e cosa non può fare
*(Baseline produzione: universo EUR/ACC, operatività EOD, esecuzione differita.)*

Ecco cosa il tuo sistema può gestire perfettamente ("tutte le altre modalità"):
1. Swing Trading (Orizzonte: Giorni/Settimane)
Logica: Cerchi di catturare un movimento di breve durata (es. un rimbalzo tecnico, una rottura di resistenza).
Fattibilità: Totale. Il tuo sistema scarica i dati la sera, calcola i segnali e ti dice "Domani mattina compra in apertura".
Vantaggio: Hai il tempo (la notte) per analizzare il segnale senza stress, controllare il grafico e decidere.
Nota: Qui il costo commissionale e lo slippage pesano di più. Il tuo modulo di reporting sarà fondamentale per capire se ne vale la pena.
2. Trend Following (Orizzonte: Settimane/Mesi)
Logica: "Il trend è tuo amico". Usi medie mobili (es. SMA 200) o breakout dei massimi a 20 giorni. Stai dentro finché il trend regge.
Fattibilità: È lo scenario ideale per questo progetto.
Vantaggio: Meno operazioni, meno stress, meno commissioni. Il Risk Management (guardrails) qui lavora benissimo per proteggerti dai crolli prolungati.
3. Rotazione Settoriale / Momentum (Orizzonte: Mensile)
Logica: Ogni fine mese guardi il tuo universo ETF (Tecnologia, Energy, Gold, Bond) e compri solo i 2 o 3 più forti (Momentum relativo).
Fattibilità: Molto alta. I calcoli di Ranking si fanno facilmente in SQL/Pandas sui dati storici.
Vantaggio: È una strategia classica che storicamente funziona bene e richiede poco tempo (ribilanciamento periodico).
4. Mean Reversion "Lenta" (Orizzonte: Giorni)
Logica: "È sceso troppo, deve risalire". Compri quando l'RSI è a terra o il prezzo tocca la banda di Bollinger inferiore.
Fattibilità: Sì, ma con un vincolo: operando EOD (End Of Day), entri il giorno dopo il segnale. A volte ti perdi il rimbalzo immediato, ma eviti anche di "afferrare il coltello mentre cade".
Il vero limite (e perché è un bene)
La tua architettura ti impone un vincolo operativo salutare: l'Esecuzione Differita (T+1 Open o T+0 Close).
Non puoi reagire alla notizia uscita alle 14:30.
Non puoi vendere per panico alle 11:00 perché il mercato fa -2%.
Questo vincolo tecnico diventa un vantaggio psicologico. Ti costringe alla disciplina. Il sistema "pensa" a bocce ferme, la sera, a mercati chiusi. Tu esegui la mattina dopo. Questo filtro elimina il 90% degli errori emotivi che distruggono i portafogli retail.
Conclusione:
Sì, il progetto supporta tutto ciò che non è "tempo reale". È una macchina da guerra per gestire il patrimonio seriamente, spaziando dall'investimento pigro (Buy & Hold) allo speculativo ragionato (Swing), mantenendo sempre il controllo del rischio e della fiscalità.

---
---

## 1. Architettura del Sistema

### 1.1 Stack vincolato
- **DB Core:** DuckDB, file singolo `data/etf_data.duckdb`.
- **Runtime:** Python (CLI scripts).
- **Storage analytics:** Parquet per snapshot/export e Run Package su filesystem.
- **OS target:** Windows native.

### 1.2 Flusso dati (EOD) - CLOSED LOOP
1) Ingestione prezzi (provider → staging → merge in `market_data`).
2) Validazione + audit (`ingestion_audit`, policy revised history).
3) Calcolo metriche/indicatori (DuckDB SQL + Python).
4) **Signal Engine** → `signals` table (compute_signals.py).
5) **Strategy Engine** → ordini JSON (strategy_engine.py).
6) **🆕 Execute Orders Bridge** → `fiscal_ledger` + `trade_journal` (execute_orders.py).
7) **Ledger Update** → cash interest + sanity check (update_ledger.py).
8) **🆕 Complete Cycle Orchestration** (run_complete_cycle.py).
9) Report e Run Package serializzato.

**Nota:** Il sistema è ora un vero closed loop con catena di esecuzione completa da segnali a movimenti ledger.


---

## 2. Modellazione dati e calcolo

### 2.1 Convenzioni di prezzo
- **Segnali/analisi:** usare `adj_close` per continuità (total-return tecnico, utile per indicatori).  
- **Ledger/valorizzazione portafoglio:** usare `close` (prezzo “raw” di mercato).  
Motivazione: `adj_close` può incorporare distribuzioni in modo non adatto alla contabilizzazione cash per ETF a distribuzione (vedi §3.6 e §6.5).

### 2.2 Window functions e calcoli
Indicatori (SMA, vol, drawdown, ecc.) preferibilmente in SQL, con funzioni finestra.

---

## 3. Data Governance e Data Quality

### 3.1 Audit di ingestione
Ogni ingestione produce record in `ingestion_audit` (provider, range date, accepted/rejected, motivazioni).

### 3.2 Revised history (soft vs hard)
- **Soft revision**: variazione relativa < `revision_tol_pct` (default 0.5%) → log warning, non blocca.
- **Hard revision**: ≥ soglia → richiede intervento (force reload / accettazione esplicita).
- **Retail policy**: Qualsiasi revisione > 0% deve fermare il ciclo (investigazione manuale).

### 3.3 Multi-provider e normalizzazione schema
Se il provider fallback viene usato, i dati devono passare da normalizzazione (stessa semantica `close/adj_close/volume/currency`).  
Audit registra `provider_schema_hash`.

### 3.4 Trading calendar
`trading_calendar` definisce giorni di negoziazione (is_open) per le borse di riferimento.  
Usi: validazione gap reali, rolling windows, “missing data” continuity check.

#### 3.4.1 Spike detection (per simbolo, config-driven)
Oltre ai check di coerenza, applicare una soglia massima di movimento giornaliero **per simbolo**:
- Campo: `max_daily_move_pct` in `config/etf_universe.json` (default **15%** se assente).
- Regola: se `ABS(close_t / close_{t-1} - 1) > max_daily_move_pct` → record **SCARTATO** e motivazione registrata in `ingestion_audit.reject_summary`.

Scopo: ridurre falsi positivi/negativi e mantenere il controllo “retail-serio” senza dinamiche complesse.
Cross-Ref: DATADICTIONARY DD-3.2, DD-5.1; TODOLIST TL-2.6.

### 3.5 Protezione “Zombie Price”
Caso tipico: provider ripete lo stesso `close` per giorni con `volume=0`.  
Requisito: tali giorni **non** devono ridurre artificialmente la volatilità; vengono marcati e esclusi dai calcoli di rischio, o trattati come missing.

### 3.6 Corporate actions e dividendi (lean)
`corporate_actions` è opzionale ma abilita warning minimi su dividendi e split.  
Per ETF a distribuzione, la contabilizzazione dei dividendi richiede flusso cash (vedi §6.5).

---

## 4. Strategy & Signal Engine

### 4.1 Modulo Signal Engine
Il sistema deve calcolare segnali oggettivi in `strategies/alpha_signals.py` (o equivalente).  
Output minimo standardizzato:
- `signal_state` (RISK_ON / RISK_OFF / HOLD)
- `risk_scalar` (0..1)
- `explain_code` (stringa corta)

### 4.2 Baseline Strategy (SMA 200/50 Crossover)
**Implementazione obbligatoria per edge verificato:**
- **Signal primario**: SMA 200/50 crossover con regime filter
- **Regime filter**: Solo RISK_ON se SPY > SMA 200 (bear market guard)
- **Target Sharpe**: > 0.7 su 10+ anni walk-forward analysis
- **Requisito**: Edge verificato prima di produzione

**Componenti strategia:**
```python
# Trend detection
if price > sma_50 and sma_50 > sma_200:
    signal_state = 'RISK_ON'
elif price < sma_50 and sma_50 < sma_200:
    signal_state = 'RISK_OFF'
else:
    signal_state = 'HOLD'

# Regime filter
if spy_close < spy_sma_200:
    signal_state = 'RISK_OFF'  # Bear market guard
```

### 4.3 Signal Diversification (futura)
- **Mean Reversion**: RSI extremes (oversold/overbought)
- **Momentum**: 12-month momentum ranking
- **Regime-based weighting**: Low vol → momentum, high vol → mean reversion

### 4.4 Override discipline
Se l’operatore inserisce ordini che contraddicono il segnale automatico:
- `trade_journal.flag_override = TRUE`
- `override_reason` obbligatorio (stringa corta)

### 4.5 Inerzia “tax-friction aware” (smart retail)
Quando una riallocazione implica realizzo di gain tassabili o costi elevati:
- calcolare `tax_friction_est + fees_est`
- se `(expected_alpha - total_cost) < inertia_threshold` → **nessuna azione** (HOLD)
Scopo: massimizzare rendimento netto tramite differimento d’imposta quando razionale.

Output richiesto in `orders.json` (EP-07):
- `expected_alpha_est`, `fees_est`, `tax_friction_est`
- `do_nothing_score` (quanto conviene non agire)
- `recommendation` = `HOLD` / `TRADE` (decisione proposta dal motore)

Cross-Ref: DATADICTIONARY DD-12.4, TODOLIST TL-1.2 e TL-3.1.

---

## 5. Execution Model & Risk Engine

### 5.1 Execution model
Default: **T+1_OPEN** per backtest difendibile. Opzionale: T+0_CLOSE (solo con cost model adeguato).

### 5.2 Cost Model Realistico (CRITICO)
**TER drag giornaliero:** Applicare come drag continuo, non solo annuale.
```python
# TER drag giornaliero
ter_daily = (1 + ter) ** (1/252) - 1
adj_return = raw_return - ter_daily
```
**Impatto:** 2% CAGR in 10 anni (non 0.2% come in config).

**Slippage dinamico:** Basato su volatilità e volume.
```python
# Slippage dinamico (bps)
vol_20d = annualized_volatility_20d
slippage_bps = max(2, vol_20d * 0.5)  # min 2 bps
```

**Commissioni realistiche:** Min commission bias per retail.
```python
# Commissioni minime (es. Interactive Brokers)
if trade_value < 1000:
    commission = max(5.0, trade_value * commission_pct)
else:
    commission = trade_value * commission_pct
```

### 5.3 Slippage monitoring
Nel journal: `theoretical_price` vs `realized_price` e `slippage_bps`.

### 5.4 Guardrails
- Spy/benchmark guard (configurabile)
- Volatility regime alert (es. 25% come “crisi”), breaker separato e default OFF
- Floor su sizing per evitare paralisi: `risk_scalar = max(floor, min(1.0, target_vol/current_vol))`

---

## 6. Fiscal Engine (Italia) — Requisiti chiave

### 6.1 PMC e ledger
PMC ponderato continuo su quantità; arrotondamenti contabili a 0.01 EUR via `ROUND(x, 2)` nelle query fiscali.

### 6.2 Distinzione categoria fiscale per strumento (CRITICO)
Ogni strumento deve avere una `tax_category` (da config o registry):
- `OICR_ETF` (tipico ETF/fondi): **gain** trattato come reddito di capitale → tassazione piena 26% **senza** compensazione con zainetto; **loss** come reddito diverso → va nello zainetto (se applicabile in regime simulato).
- `ETC_ETN_STOCK` (semplificazione): gain/loss come redditi diversi → **compensazione** con zainetto consentita nel modello.

**Chiarimento operativo (baseline EUR/ACC):** se l’universo contiene solo strumenti `OICR_ETF`, lo zainetto può **accumularsi** (per loss) ma **non** riduce i gain/proventi degli ETF. Diventa “utilizzabile” solo se/quando si abilitano strumenti `ETC_ETN_STOCK` (feature flag / universo esteso).

> Nota: il sistema è una simulazione; l’utente resta responsabile della verifica con intermediario/consulente.

### 6.3 Zainetto fiscale (minusvalenze) e scadenza corretta
Minus nello zainetto scadono al **31/12 del 4° anno successivo** a quello di realizzo (non “created_at + 4 anni”).  
`expires_at = DATE(year(realize_date)+4, 12, 31)`.

### 6.4 FX e capital gain in EUR (quando currency != EUR)
**Baseline EUR/ACC:** questa sezione è disattivata; l’ingestione blocca strumenti non-EUR salvo feature flag FX.

Per strumenti in valuta diversa da EUR, il ledger deve storicizzare:
- `trade_currency`
- `exchange_rate_used` (FX verso EUR alla data operazione)
- `price_eur`
Il gain fiscale è calcolato su controvalori EUR: la componente FX può generare gain tassabile.

### 6.5 Dividendi / proventi (ETF a distribuzione)
**Baseline EUR/ACC:** `dist_policy=ACC` per tutti gli strumenti; flussi dividendo cash non previsti. La sezione resta per estensioni future.

- Se lo strumento è `DIST`, i proventi generano cash e tassazione immediata (aliquota 26% nel modello).  
- Se lo strumento è `ACC`, non si registrano proventi cash (il NAV/prezzo riflette reinvestimento).

Requisito minimo: distinguere `dist_policy` e usare `close` per valorizzazione; dividendi cash solo se disponibili (provider o `corporate_actions`), altrimenti warning “dividend not modeled”.

### 6.6 Cash interest
Evento `INTEREST` mensile su `cash_balance`, con tasso configurabile.  
**CRITICO per realismo CAGR**: cash 3.5% genera +0.5% CAGR netto su portafoglio.  
Implementazione obbligatoria in baseline EUR/ACC.

| Parametro | Default | Note |
|---|---|---|
| `cash_interest_rate` | 0.02 | 2% annualizzato (configurabile) |
| `cash_interest_monthly` | true | Accrual mensile su `fiscal_ledger` |
| `rounding` | 0.01 EUR | Arrotondamento contabile |

**Implementazione:**
```python
# Monthly accrual in update_ledger.py
monthly_rate = config['fiscal']['cash_interest_rate'] / 12
interest_amount = cash_balance * monthly_rate
# Insert INTEREST record in fiscal_ledger
```

---

## 7. Reporting & Run Package serializzato (Performance Report)

### 7.1 Run Package (obbligatorio)
Ogni run che produce KPI deve scrivere:
- `data/reports/<run_id>/manifest.json`
- `data/reports/<run_id>/kpi.json`
- `data/reports/<run_id>/summary.md`

Se manca un artefatto obbligatorio → run invalida (exit code != 0).

### 7.2 Contenuti minimi
- Parametri run (execution model, cost model, tax model, universe)
- `config_hash` e `data_fingerprint` (input tracciabili)
- KPI e `kpi_hash`
- Collegamenti ad audit/ledger
- Se presente journaling: sezione “Forecast vs Postcast” e “Emotional Gap” (vedi §7.3)

#### 7.2.1 Benchmark “apples-to-apples” (indice vs ETF investibile)
- **Benchmark consigliato (default):** un **ETF UCITS EUR/ACC** investibile e comparabile (stessa valuta e policy di distribuzione).
- **Indice non investibile (es. `^GSPC`)**: usarlo come *market proxy* / regime filter è lecito, ma nel reporting **non** applicare tassazione simulata “da realizzo”.  
  In tal caso il benchmark può includere solo:
  - FX (se abilitato),  
  - TER proxy (se si vuole un friction proxy),  
  - slippage/fees indicative.  
- **ETF benchmark investibile:** la tassazione simulata segue `tax_category` (es. `OICR_ETF` = gain tassato pieno, senza compensazione zainetto).

Requisito: il `manifest.json` deve indicare `benchmark_symbol` e `benchmark_kind` (`ETF`/`INDEX`) per evitare ambiguità nei KPI.
Cross-Ref: DATADICTIONARY DD-8.2, DD-10.3, DD-11.1; TODOLIST TL-2.7.

### 7.3 Emotional Gap (serietà)
Nel `summary.md` includere confronto:
- PnL “Strategia Pura” (segnali, senza override)
- PnL “Strategia Reale” (con override)
Se gap < 0: evidenziare esplicitamente il costo degli interventi manuali.

---

## 8. Operations

### 8.1 Manual gate e commit
Il flusso standard è:
1) ingest
2) health + sanity + guardrails
3) dry-run ordini
4) review manuale (se warning/breaker)
5) backup
6) commit ledger (`--commit`)

### 8.2 Backup, restore, maintenance
- Backup DB pre-commit e a fine sessione.
- Restore via script “file copy”.
- Maintenance periodica: `CHECKPOINT` per consolidare e limitare crescita del file.

---

## 9. Testing & Validation

### 9.1 Sanity check (bloccante)
**CRITICO:** Sanity check deve bloccare commit se fallisce.
Invarianti minime:
- nessuna posizione negativa / qty < 0
- cash/equity incoerenti (invarianti contabili)
- violazione "no future data leak" rispetto all'execution model
- gap su giorni `is_open=TRUE` (trading_calendar)
- mismatch ledger vs market_data su date/symbol

**Implementazione obbligatoria:**
```python
# In update_ledger.py --commit
if not sanity_check.run():
    print("SANITY FAILED: Aborting commit.")
    sys.exit(1)
```

### 9.2 Stress test (smoke)
Backtest su finestre di crisi + worst rolling (12/24 mesi), con output in run package.

### 9.3 Monte Carlo Smoke Test (semplice)
**Implementazione obbligatoria per validazione rischio coda:**
```python
# Shuffle test semplice (1000 iterazioni)
for i in range(1000):
    shuffled_returns = np.random.permutation(returns)
    cagr, max_dd = calculate_metrics(shuffled_returns)
    results.append((cagr, max_dd))

# 5th percentile MaxDD check
max_dd_5pct = np.percentile([r[1] for r in results], 5)
if max_dd_5pct > 0.25:  # 25% max drawdown
    print("STRATEGY TOO VOLATILE for retail")
```
**Target:** 5th percentile MaxDD < 25% per retail risk tolerance.

---

## 10. Cross-Reference (indice rapido)
- Data schema: vedi DATADICTIONARY (DD-*)  
- Piano implementazione: vedi TODOLIST (TL-*)  
- Comandi operativi: vedi README (EP-*)
