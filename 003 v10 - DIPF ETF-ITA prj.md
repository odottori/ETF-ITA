# DIPF - Design & Implementation Plan Framework (ETF_ITA)

**Progetto:** ETF Italia Smart Retail  
**Package:** v10.8.0 (naming canonico)  
**Doc Revision:** r40 — 2026-01-07  
**Engine:** DuckDB (embedded OLAP)  
**Runtime:** Python 3.10+ (Windows)  
**Stato Documento:** 🟢 CANONICO — PRODUCTION READY v10.8.0  
**Stato Sistema:** PRODUCTION READY  
**Baseline produzione:** EUR / ACC (FX e DIST disattivati salvo feature flag)

---

## 0. Executive Summary (Visione d'insieme)

### 0.1 Missione
Costruire un sistema "smart retail" per gestione e simulazione di un portafoglio ETF/strumenti assimilati per residenti italiani, con tre obiettivi simultanei:
1) **Affidabilità operativa** (audit, sanity check, health check, continuità).  
2) **Realismo fiscale e reporting netto** (PMC, tassazione, zainetto dove applicabile, dividenti/cash).  
3) **Disciplina e misurabilità decisionale** (Signal Engine oggettivo + Trade Journaling Forecast/Postcast).

### 0.2 Obiettivi misurabili
- **Riproducibilità**: ogni run produce un *Run Package* serializzato con `run_id`, parametri, KPI e hash (vedi §7).  
- **Fail-fast**: sanity check bloccante su invarianti contabili e su leakage dei dati futuri (vedi §9).  
- **Coerenza fiscale**: distinzione per categoria fisale (ETF/OICR vs strumenti "redditi diversi") e scadenza corretta minus (vedi §6).  
- **Data Quality**: policy soft/hard per revised history e protezione "zombie prices" (vedi §3).

### 0.3 Aspettative realistiche (performance)
Il progetto privilegia **robustezza e coerenza** su aggressività. Non assume target di rendimento fisso (es. 20% annuo).  
La strategia è iterativa: prima un framework "difendibile", poi ottimizzazione segnali e sizing.

### 0.4 Scope e Non-Goals
**In scope:**
- **Baseline produzione:** universo **EUR / ACC** (no FX, no DIST). Strumenti non-EUR o DIST vengono rifiutati salvo abilitazione esplicita delle feature FX/DIV.
- EOD ingestion multi-provider con audit.
- Signal Engine oggettivo (baseline trend-following + risk sizing).
- Fiscal engine Italia (PMC, imposta 26%, zainetto per "redditi diversi", handling OICR).
- Reporting netto con Run Package.
- Trade journaling e attribution (Forecast/Postcast + override).

**Non-goals (rimandati):**
- Motore corporate actions completo "istituzionale".
- Monte Carlo / ottimizzazioni stocastiche.
- Integrazione broker live (ordine reale): rimane *sim/decision support*.

### 0.5 Cosa può e cosa non può fare
*(Baseline produzione: universo EUR/ACC, operatività EOD, esecuzione differita.)*

Ecco cosa il tuo sistema può gestire perfettamente ("tutte le altre modalità"):
1. **Swing Trading** (Orizzonte: Giorni/Settimane)
Logica: Cerchi di catturare un movimento di breve durata (es. un rimbalzo tecnico, una rottura di resistenza).
Fattibilità: Totale. Il tuo sistema scarica i dati la sera, calcola i segnali e ti dice "Domani mattina compra in apertura".
Vantaggio: Hai il tempo (la notte) per analizzare il segnale senza stress, controllare il grafico e decidere.
Nota: Qui il costo commissionale e lo slippage pesano di più. Il tuo modulo di reporting sarà fondamentale per capire se ne vale la pena.

2. **Trend Following** (Orizzonte: Settimane/Mesi)
Logica: "Il trend è tuo amico". Usi medie mobili (es. SMA 200) o breakout dei massimi a 20 giorni. Stai dentro finché il trend regge.
Fattibilità: È lo scenario ideale per questo progetto.
Vantaggio: Meno operazioni, meno stress, meno commissioni. Il Risk Management (guardrails) qui lavora benissimo per proteggerti dai crolli prolungati.

3. **Rotazione Settoriale / Momentum** (Orizzonte: Mensile)
Logica: Ogni fine mese guardi il tuo universo ETF (Tecnologia, Energy, Gold, Bond) e compri solo i 2 o 3 più forti (Momentum relativo).
Fattibilità: Molto alta. I calcoli di Ranking si fanno facilmente in SQL/Pandas sui dati storici.
Vantaggio: È una strategia classica che storicamente funziona bene e richiede poco tempo (ribilanciamento periodico).

4. **Mean Reversion "Lenta"** (Orizzonte: Giorni)
Logica: "È sceso troppo, deve risalire". Compri quando l'RSI è a terra o il prezzo tocca la banda di Bollinger inferiore.
Fattibilità: Sì, ma con un vincolo: operando EOD (End Of Day), entri il giorno dopo il segnale. A volte ti perdi il rimbalzo immediato, ma eviti anche di "afferrare il coltello mentre cade".

**Il vero limite (e perché è un bene)**
La tua architettura ti impone un vincolo operativo salutare: l'Esecuzione Differita (T+1 Open o T+0 Close).
Non puoi reagire alla notizia uscita alle 14:30.
Non puoi vendere per panico alle 11:00 perché il mercato fa -2%.
Questo vincolo tecnico diventa un vantaggio psicologico. Ti costringe alla disciplina. Il sistema "pensa" a bocce ferme, la sera, a mercati chiusi. Tu esegui la mattina dopo. Questo filtro elimina il 90% degli errori emotivi che distruggono i portafogli retail.

**Conclusione:**
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
3) Calcolo metriche/indicatori → `risk_metrics` vista (DuckDB SQL + window functions).
4) **Signal Engine** → `signals` table (compute_signals.py).
5) **Strategy Engine V2** → `orders_plan` + ordini TWO-PASS (strategy_engine_v2.py):
   - PASS 1: EXIT/SELL (MANDATORY: RISK_OFF, stop-loss, planned exits)
   - CASH UPDATE: Simula cash post-sell
   - PASS 2: ENTRY/REBALANCE (ranking candidati + constraints + allocation)
6) **Execute Orders Bridge** → `fiscal_ledger` + `trade_journal` (execute_orders.py):
   - Pre-trade controls: cash e position checks
   - Calcolo costi realistici: commission + slippage (volatility-adjusted)
   - Tassazione integrata: `calculate_tax()` con zainetto per categoria fiscale
7) **Ledger Update** → cash interest + sanity check (update_ledger.py).
8) **Complete Cycle Orchestration** (run_complete_cycle.py).
9) Report e Run Package serializzato (session-based).

**Nota:** Il sistema è un vero closed loop con catena di esecuzione completa da segnali a movimenti ledger. Holding period dinamico (5-30 giorni) integrato in strategy_engine_v2.

### 1.3 Operational Modes (Period Matrix) — concetti
Il sistema supporta più modalità di periodo per **Signal Engine** e **Backtest**. Nel DIPF si definiscono i concetti (non i flag CLI):

- **FULL**: intero storico disponibile (baseline per analisi di lungo periodo).
- **RECENT**: finestra mobile (rolling window) per monitoraggio e regressioni veloci.
- **PRESET**: periodi critici standardizzati (es. GFC, Euro-crisis, COVID, Inflation 2022).
- **RANGE**: intervallo esplicito `start_date` → `end_date` per test mirati.

**Riferimenti operativi (comandi/flag):**
- README: EP-05 (Compute Signals) e EP-11/EP-15 (Backtest)
- TODOLIST: EP-05b/EP-05c e EP-15b/EP-15c

**Semaforica:** le modalità avanzate (matrix `FULL/RECENT/PRESET/ALL`) restano *candidate* finché non validate end-to-end con report e Run Package riproducibile.

---

## 2. Modellazione dati e calcolo

### 2.1 Convenzioni di prezzo
- **Segnali/analisi:** usare `adj_close` per continuità (total-return tecnico, utile per indicatori).  
- **Ledger/valorizzazione portafoglio:** usare `close` (prezzo "raw" di mercato).  
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
Usi: validazione gap reali, rolling windows, "missing data" continuity check.

#### 3.4.1 Spike detection (per simbolo, config-driven)
Oltre ai check di coerenza, applicare una soglia massima di movimento giornaliero **per simbolo**:
- Campo: `max_daily_move_pct` in `config/etf_universe.json` (default **15%** se assente).
- Regola: se `ABS(close_t / close_{t-1} - 1) > max_daily_move_pct` → record **SCARTATO** e motivazione registrata in `ingestion_audit.reject_summary`.

Scopo: ridurre falsi positivi/negativi e mantenere il controllo "retail-serio" senza dinamiche complesse.

### 3.5 Protezione "Zombie Price"
Caso tipico: provider ripete lo stesso `close` per giorni con `volume=0`.  
Requisito: tali giorni **non** devono ridurre artificialmente la volatilità; vengono marcati e esclusi dai calcoli di rischio, o trattati come missing.

### 3.6 Corporate actions e dividendi (lean)
`corporate_actions` è opzionale ma abilita warning minimi su dividendi e split.  
Per ETF a distribuzione, la contabilizzazione dei dividendi richiede flusso cash (vedi §6.5).

---

## 4. Strategy & Signal Engine

### 4.1 Modulo Signal Engine (IMPLEMENTATO)
**File**: `scripts/data/compute_signals.py`  
**Output standardizzato** in tabella `signals`:
- `signal_state` (RISK_ON / RISK_OFF / HOLD)
- `risk_scalar` (0..1) con volatility targeting
- `explain_code` (stringa corta)
- `sma_200`, `volatility_20d`, `spy_guard`, `regime_filter`

**Logica implementata**:
- **Trend Following**: SMA 200 con banda 2% (price > sma_200 * 1.02 → RISK_ON)
- **Volatility Regime Filter**: Adjustment risk_scalar per alta/bassa volatilità
- **Drawdown Protection**: Force RISK_OFF se drawdown > 15%
- **SPY Guard**: Bear market guard (SPY < SMA 200 → block RISK_ON)
- **Entry-Aware Stop-Loss**: Check stop-loss basato su entry_price
- **Risk Scalar Volatility Targeting**: `vol_scalar = target_vol / current_vol` (clamped)

### 4.2 Strategy Engine V2 (IMPLEMENTATO)
**File**: `scripts/trading/strategy_engine_v2.py`  
**Design**: TWO-PASS Workflow (Exit → Cash Update → Entry)

**PASS 1 - EXIT/SELL (MANDATORY FIRST)**:
- MANDATORY exits: RISK_OFF / stop-loss / guardrails
- Planned exits: `today >= expected_exit_date` (holding period)
- Pre-trade checks: oversell protection, qty > 0
- Output: `orders_plan` (SELL) con `decision_path` e `reason_code`

**CASH UPDATE (simulato)**:
- Simula cash post-sell per entry allocation realistica

**PASS 2 - ENTRY/REBALANCE (OPPORTUNISTIC + FORCED)**:
- Genera candidati entry/rebalance da segnali RISK_ON
- Calcola `candidate_score` (0..1): momentum + risk_scalar - cost_penalty - overlap_penalty
- Ranking deterministico candidati
- Applica constraints hard:
  - Max positions (config)
  - Cash reserve (config)
  - Overlap underlying (forbid default)
- Alloca capitale deterministico + rounding
- Output: `orders_plan` (BUY) con `candidate_score` e `reject_reason`

**Portfolio Construction** (`scripts/strategy/portfolio_construction.py`):
- `calculate_expected_holding_days()`: Holding period dinamico 5-30 giorni
  - Logica INVERTITA: alto momentum/risk/vol = holding CORTO
- `calculate_candidate_score()`: Score composito per ranking
- `calculate_cost_penalty()`: TER + slippage normalizzato
- `calculate_overlap_penalty()`: Forbid overlap underlying
- `filter_by_constraints()`: Filtri hard (max positions, cash reserve)
- `calculate_qty()`: Allocazione deterministico + rounding

### 4.3 Holding Period Dinamico (IMPLEMENTATO)
**File**: `scripts/strategy/portfolio_construction.py`  
**Range**: 5-30 giorni (swing trading multi-day)

**Logica INVERTITA** (prendi profitto veloce su momentum forte):
- Alto momentum/risk/vol → holding CORTO (5-10 giorni)
- Basso momentum/risk/vol → holding LUNGO (20-30 giorni)

**Adjustments**:
- `risk_adj`: RISK_OFF = 1.5x (aspetta recovery), RISK_ON = 0.7-1.0x
- `vol_adj`: Alta vol (>25%) = 0.6x (exit veloce), Bassa vol = 1.0x
- `momentum_adj`: Momentum forte (>0.85) = 0.7x (prendi profitto), Debole = 1.2x

**Schema DB** (tracking completo):
- `fiscal_ledger`: 6 campi holding period (entry_date, entry_score, expected_holding_days, expected_exit_date, actual_holding_days, exit_reason)
- `position_plans`: Piano holding period per simbolo
- `position_events`: Eventi extend/close con motivo
- `position_peaks`: Peak tracking per trailing stop

### 4.4 Override discipline (IMPLEMENTATO)
**Tabella**: `trade_journal`  
- `flag_override = TRUE` se ordine manuale
- `override_reason` obbligatorio

### 4.5 Tax-Friction Aware Logic (IMPLEMENTATO)
**Cost Penalty** integrato in `candidate_score`:
- `cost_penalty = (ter + slippage_roundtrip) / 0.01` (normalizzato 0-1)
- `overlap_penalty = 1.0` se overlap underlying detected
- `candidate_score = momentum * risk_scalar * (1 - cost_penalty) * (1 - overlap_penalty)`

**Logica MANDATORY vs OPPORTUNISTIC** (strategy_engine.py):
- MANDATORY: stop-loss, force rebalancing (sempre eseguiti)
- OPPORTUNISTIC: rebalancing solo se `trade_score >= score_rebalance_min`
- ENTRY: nuove posizioni solo se `momentum_score >= score_entry_min`

**Output** in `orders_plan`:
- `candidate_score` (0..1)
- `decision_path` (es. 'MANDATORY_EXIT', 'OPPORTUNISTIC_ENTRY')
- `reason_code` (es. 'STOP_LOSS', 'PLANNED_EXIT', 'RISK_ON_ENTRY')
- `reject_reason` (se rifiutato: 'CASH_RESERVE', 'MAX_POSITIONS', 'OVERLAP')

---

## 5. Execution Model & Risk Engine

### 5.1 Execution model
Default: **T+1_OPEN** per backtest difendibile. Opzionale: T+0_CLOSE (solo con cost model adeguato).

### 5.2 Cost Model Realistico (IMPLEMENTATO)
**File**: `scripts/utils/universe_helper.py`, `execute_orders.py`, `backtest_engine.py`

**Commissioni** (implementato):
```python
commission_pct = config['universe']['core'][0]['cost_model']['commission_pct']
commission = position_value * commission_pct
if position_value < 1000:
    commission = max(5.0, commission)  # Minimum €5
```

**Slippage dinamico** (implementato con volatility adjustment):
```python
volatility = get_volatility_20d(symbol)  # Da risk_metrics
slippage_bps = config['cost_model']['slippage_bps']
slippage_bps = max(slippage_bps, volatility * 0.5)  # Volatility adjustment
slippage = position_value * (slippage_bps / 10000)
```

**TER drag** (implementato in strategy_engine.py):
```python
ter = config['universe']['core'][0]['ter']
ter_daily = (1 + ter) ** (1/252) - 1
ter_drag = position_value * ter_daily
```

**Total cost** = commission + slippage + ter_drag (per trade)

### 5.3 Slippage monitoring
Nel journal: `theoretical_price` vs `realized_price` e `slippage_bps`.

### 5.4 Guardrails
- Spy/benchmark guard (configurabile)
- Volatility regime alert (es. 25% come "crisi"), breaker separato e default OFF
- Floor su sizing per evitare paralisi: `risk_scalar = max(floor, min(1.0, target_vol/current_vol))`

---

## 6. Fiscal Engine (Italia) — IMPLEMENTATO

### 6.1 Tax Engine (IMPLEMENTATO)
**File**: `scripts/fiscal/tax_engine.py`  
**Conformità**: DIPF §6.2, normativa italiana

**Funzioni**:
- `calculate_tax()`: Calcolo tassazione 26% con zainetto per categoria fiscale
- `create_tax_loss_carryforward()`: Creazione zainetto con scadenza 31/12/(anno+4)
- `update_zainetto_usage()`: Aggiornamento used_amount FIFO
- `get_available_zainetto()`: Query zainetto disponibile per categoria

### 6.2 Distinzione categoria fiscale (IMPLEMENTATO)
**Schema**: `symbol_registry.tax_category`, `tax_loss_carryforward.tax_category`

**Logica implementata**:
- **OICR_ETF** (default): 
  - Gain tassati pieni 26% SENZA compensazione zainetto
  - Loss accumulate in zainetto ma NON utilizzabili per compensare gain OICR_ETF
  - Zainetto diventa utilizzabile solo con strumenti ETC_ETN_STOCK
- **ETC_ETN_STOCK**: 
  - Gain/loss come redditi diversi
  - Compensazione zainetto consentita per categoria fiscale

**Query zainetto** (per categoria, non per simbolo):
```python
zainetto_available = conn.execute("""
    SELECT COALESCE(SUM(loss_amount) + SUM(used_amount), 0)
    FROM tax_loss_carryforward 
    WHERE tax_category = ? 
    AND used_amount < ABS(loss_amount)
    AND expires_at > ?
""", [tax_category, realize_date]).fetchone()[0]
```

### 6.3 Zainetto fiscale e scadenza (IMPLEMENTATO)
**Tabella**: `tax_loss_carryforward`  
**Scadenza**: 31/12 del 4° anno successivo (conforme normativa italiana)

**Implementazione**:
```python
realize_year = realize_date.year
expiry_year = realize_year + 4
expires_at = datetime(expiry_year, 12, 31).date()
```

**Aggiornamento FIFO** (used_amount):
- Ordina zainetti per `expires_at ASC, id ASC`
- Consuma zainetto più vecchio prima
- Traccia `used_amount` per ogni record

### 6.4 PMC e Ledger (IMPLEMENTATO)
**Schema**: `fiscal_ledger` (26 colonne)  
**Campi fiscali**:
- `pmc_snapshot`: PMC snapshot alla data
- `tax_paid`: Imposta pagata (26%)
- `fees`: Commissioni + slippage
- `trade_currency`, `exchange_rate_used`, `price_eur` (per FX future)

**Arrotondamenti**: 0.01 EUR via `Decimal.quantize(Decimal('0.01'))`

### 6.4 FX e capital gain in EUR (quando currency != EUR)
**Baseline EUR/ACC:** questa sezione è disattivata; l'ingestione blocca strumenti non-EUR salvo feature flag FX.

Per strumenti in valuta diversa da EUR, il ledger deve storicizzare:
- `trade_currency`
- `exchange_rate_used` (FX verso EUR alla data operazione)
- `price_eur`
Il gain fiscale è calcolato su controvalori EUR: la componente FX può generare gain tassabile.

### 6.5 Dividendi / proventi (ETF a distribuzione)
**Baseline EUR/ACC:** `dist_policy=ACC` per tutti gli strumenti; flussi dividendo cash non previsti. La sezione resta per estensioni future.

- Se lo strumento è `DIST`, i proventi generano cash e tassazione immediata (aliquota 26% nel modello).  
- Se lo strumento è `ACC`, non si registrano proventi cash (il NAV/prezzo riflette reinvestimento).

Requisito minimo: distinguere `dist_policy` e usare `close` per valorizzazione; dividendi cash solo se disponibili (provider o `corporate_actions`), altrimenti warning "dividend not modeled".

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
- Se presente journaling: sezione "Forecast vs Postcast" e "Emotional Gap" (vedi §7.3)

#### 7.2.1 Benchmark "apples-to-apples" (indice vs ETF investibile)
- **Benchmark consigliato (default):** un **ETF UCITS EUR/ACC** investibile e comparabile (stessa valuta e policy di distribuzione).
- **Indice non investibile (es. `^GSPC`)**: usarlo come *market proxy* / regime filter è lecito, ma nel reporting **non** applicare tassazione simulata "da realizzo".  
  In tal caso il benchmark può includere solo:
  - FX (se abilitato),  
  - TER proxy (se si vuole un friction proxy),  
  - slippage/fees indicative.  
- **ETF benchmark investibile:** la tassazione simulata segue `tax_category` (es. `OICR_ETF` = gain tassato pieno, senza compensazione zainetto).

Requisito: il `manifest.json` deve indicare `benchmark_symbol` e `benchmark_kind` (`ETF`/`INDEX`) per evitare ambiguità nei KPI.

### 7.3 Emotional Gap (serietà)
Nel `summary.md` includere confronto:
- PnL "Strategia Pura" (segnali, senza override)
- PnL "Strategia Reale" (con override)
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
- Restore via script "file copy".
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
- Data schema: vedi DATADICTIONARY  
- Piano implementazione: vedi TODOLIST  
- Comandi operativi: vedi README  
- Regole operative: vedi AGENT_RULES (v10.5.0)
