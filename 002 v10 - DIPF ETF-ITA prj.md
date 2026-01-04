# DIPF - Documento di Indirizzo e Progettazione Funzionale (ETF_ITA)

**Progetto:** ETF Italia Smart Retail  
**Package:** v10 (naming canonico)  
**Doc Revision (internal):** r22 — 2026-01-04  
**Engine:** DuckDB (embedded OLAP)  
**Runtime:** Python 3.10+ (Windows)  
**Stato:** APPROVED FOR DEV (con requisiti "backtest-grade")

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

### 1.2 Flusso dati (EOD)
1) Ingestione prezzi (provider → staging → merge in `market_data`).
2) Validazione + audit (`ingestion_audit`, policy revised history).
3) Calcolo metriche/indicatori (DuckDB SQL + Python).
4) Guardrails + pianificazione ordini (dry-run di default).
5) Commit ledger (solo con `--commit` + backup pre-commit).
6) Report e Run Package serializzato.

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
- **Soft revision:** variazione relativa < `revision_tol_pct` (default 0.5%) → log warning, non blocca.
- **Hard revision:** ≥ soglia → richiede intervento (force reload / accettazione esplicita).

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

### 4.2 Override discipline
Se l’operatore inserisce ordini che contraddicono il segnale automatico:
- `trade_journal.flag_override = TRUE`
- `override_reason` obbligatorio (stringa corta)

### 4.3 Inerzia “tax-friction aware” (smart retail)
Quando una riallocazione implica realizzo di gain tassabili o costi elevati:
- calcolare `tax_friction_est + fees_est`
- se `(expected_alpha - total_cost) < inertia_threshold` → **nessuna azione** (HOLD)
Scopo: massimizzare rendimento netto tramite differimento d’imposta quando razionale.

Output richiesto in `orders.json` (EP-07):
- `expected_alpha_est`, `fees_est`, `tax_friction_est`
- `do_nothing_score` (quanto conviene non agire)
- `recommendation` = `HOLD` / `TRADE` (decisione proposta dal motore)

Cross-Ref: DATADICTIONARY DD-11.4, TODOLIST TL-1.2 e TL-3.1.

---

## 5. Execution Model & Risk Engine

### 5.1 Execution model
Default: **T+1_OPEN** per backtest difendibile. Opzionale: T+0_CLOSE (solo con cost model adeguato).

### 5.2 Slippage monitoring
Nel journal: `theoretical_price` vs `realized_price` e `slippage_bps`.

### 5.3 Guardrails
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
Opzionale: parcheggio cash su “cash-equivalent ticker” (feature flag).

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
Invarianti minime:
- nessuna posizione negativa
- cash/equity coerenti
- no future data leak (rispetto execution model)
- coerenza tra market_data e ledger dates (trading_calendar)

### 9.2 Stress test (smoke)
Backtest su finestre di crisi + worst rolling (12/24 mesi), con output in run package.

---

## 10. Cross-Reference (indice rapido)
- Data schema: vedi DATADICTIONARY (DD-*)  
- Piano implementazione: vedi TODOLIST (TL-*)  
- Comandi operativi: vedi README (EP-*)
