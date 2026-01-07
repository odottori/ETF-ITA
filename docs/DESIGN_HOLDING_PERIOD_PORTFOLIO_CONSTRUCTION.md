# Design Document: Holding Period Dinamico + Portfolio Construction

**Versione:** 1.0  
**Data:** 2026-01-07  
**Autore:** Sistema ETF-ITA v10  
**Status:** DRAFT (in revisione)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Gap Architetturali Identificati

Il sistema attuale presenta due gap critici che spiegano l'execution rate basso (3.59%) e il cash gating cronico:

1. **Mancanza di Holding Period Dinamico**
   - Le posizioni restano aperte indefinitamente fino a RISK_OFF o stop-loss
   - Nessun "exit pianificato" → portfolio sempre fully invested
   - Nessun "riesame scenario" a scadenza prevista

2. **Mancanza di Portfolio Construction Logic**
   - Con N segnali RISK_ON simultanei, nessun criterio di selezione
   - Nessuna logica di allocation quando ci sono già posizioni aperte
   - Nessun constraint su max posizioni o cash reserve

### 1.2 Soluzione Proposta

Implementare un'architettura integrata che include:

- **Holding Period Dinamico**: durata investimento calcolata da risk_scalar, volatility, momentum
- **Portfolio Construction**: ranking candidati, selezione top-N, allocation disciplinata
- **Cash Rotation**: exit pianificati liberano cash per nuovi entry
- **Riesame Scenario**: a scadenza holding, rivalutazione se estendere o uscire

### 1.3 Impatto Atteso

- **Execution rate:** da 3.59% a 12-18% (cash rotation disciplinata)
- **Cash gating:** eliminato (reserve 10% + exit pianificati)
- **Disciplina operativa:** holding period esplicito + riesame periodico
- **Performance:** miglioramento atteso per riduzione "buy and hold involontario"

---

## 2. ARCHITETTURA HOLDING PERIOD DINAMICO

### 2.1 Principio Base

La durata dell'investimento deve essere una **funzione delle condizioni di rischio**, esattamente come il sizing (qty).

**Formula:**
```
holding_days = base_holding * risk_adjustment * volatility_adjustment * momentum_adjustment
```

Dove:
- `base_holding = 90 giorni` (default 3 mesi, parametrizzabile)
- `risk_adjustment = f(risk_scalar)` → scenario stabile = holding lungo
- `volatility_adjustment = f(volatility)` → volatilità alta = holding breve
- `momentum_adjustment = f(momentum_score)` → trend forte = holding lungo

**Range operativo (retail-grade):**
- `min_holding_days = 30` (1 mese minimo, evita overtrading)
- `max_holding_days = 180` (6 mesi massimo, evita posizioni "dimenticate")

### 2.2 Formule Dettagliate

#### A. Risk Adjustment
```python
risk_adjustment = 0.5 + (risk_scalar * 0.5)  # Range: 0.5-1.0
```

**Razionale:**
- `risk_scalar = 1.0` → `risk_adj = 1.0` (massima convinzione → holding pieno)
- `risk_scalar = 0.5` → `risk_adj = 0.75` (media convinzione → holding ridotto 25%)
- `risk_scalar = 0.2` → `risk_adj = 0.6` (bassa convinzione → holding ridotto 40%)

#### B. Volatility Adjustment
```python
if volatility > 0.20:  # > 20%
    vol_adj = 0.7      # Holding ridotto 30%
elif volatility > 0.15:  # 15-20%
    vol_adj = 0.85     # Holding ridotto 15%
else:  # < 15%
    vol_adj = 1.0      # Holding pieno
```

**Razionale:**
- Volatilità alta → scenario instabile → holding breve (ridurre esposizione temporale)
- Volatilità bassa → scenario stabile → holding lungo (massimizzare esposizione)

#### C. Momentum Adjustment
```python
momentum_adj = 0.7 + (momentum_score * 0.3)  # Range: 0.7-1.0
```

**Razionale:**
- `momentum_score = 0.8` → `momentum_adj = 0.94` (trend forte → holding quasi pieno)
- `momentum_score = 0.5` → `momentum_adj = 0.85` (trend medio → holding ridotto 15%)
- `momentum_score = 0.2` → `momentum_adj = 0.76` (trend debole → holding ridotto 24%)

### 2.3 Esempi Concreti

#### Scenario 1: Alta Convinzione
```
Input:
- risk_scalar = 1.0
- volatility = 12%
- momentum_score = 0.8

Calcolo:
- risk_adj = 0.5 + (1.0 * 0.5) = 1.0
- vol_adj = 1.0 (vol < 15%)
- momentum_adj = 0.7 + (0.8 * 0.3) = 0.94

holding_days = 90 * 1.0 * 1.0 * 0.94 = 85 giorni

Interpretazione: Scenario stabile, trend forte → holding quasi pieno (3 mesi)
```

#### Scenario 2: Media Convinzione
```
Input:
- risk_scalar = 0.5
- volatility = 18%
- momentum_score = 0.6

Calcolo:
- risk_adj = 0.5 + (0.5 * 0.5) = 0.75
- vol_adj = 0.85 (vol 15-20%)
- momentum_adj = 0.7 + (0.6 * 0.3) = 0.88

holding_days = 90 * 0.75 * 0.85 * 0.88 = 50 giorni

Interpretazione: Scenario incerto, volatilità media → holding ridotto (1.5 mesi)
```

#### Scenario 3: Bassa Convinzione
```
Input:
- risk_scalar = 0.2
- volatility = 25%
- momentum_score = 0.3

Calcolo:
- risk_adj = 0.5 + (0.2 * 0.5) = 0.6
- vol_adj = 0.7 (vol > 20%)
- momentum_adj = 0.7 + (0.3 * 0.3) = 0.79

holding_days = 90 * 0.6 * 0.7 * 0.79 = 30 giorni (clamped a min)

Interpretazione: Scenario instabile, trend debole → holding minimo (1 mese)
```

### 2.4 Logica Riesame Scenario

**Trigger riesame:**
```python
if days_held >= expected_holding_days:
    # Riesame scenario
```

**Decision tree riesame:**
```
1. Ricalcola condizioni attuali:
   - risk_scalar_current
   - volatility_current
   - momentum_score_current

2. Valuta scenario:
   IF signal_state == 'RISK_ON' AND momentum_score_current >= score_entry_min:
       # Scenario ancora favorevole
       → Calcola nuovo holding_days (con condizioni aggiornate)
       → Estendi holding: expected_exit_date = current_date + nuovo_holding
       → Log: "HOLDING_EXTENDED"
   ELSE:
       # Scenario deteriorato
       → Proponi SELL
       → Log: "EXIT_PLANNED"

3. Exit anticipato (indipendentemente da holding):
   IF signal_state == 'RISK_OFF':
       → Proponi SELL
       → Log: "EXIT_RISK_OFF"
   
   IF stop_loss_triggered:
       → Proponi SELL
       → Log: "EXIT_STOP_LOSS"
```

---

## 3. ARCHITETTURA PORTFOLIO CONSTRUCTION

### 3.1 Problema

Con N segnali RISK_ON simultanei e cash limitato, serve:
1. **Ranking**: quale candidato scegliere?
2. **Allocation**: quanto capitale allocare?
3. **Constraints**: max posizioni, cash reserve, overlap

### 3.2 Candidate Ranking

**Score composito:**
```python
candidate_score = (
    momentum_score * 0.40 +           # Trend strength (peso maggiore)
    risk_scalar * 0.30 +               # Risk-adjusted conviction
    (1 - volatility/0.30) * 0.20 +    # Stabilità (inverso vol, normalizzato)
    alpha_estimate * 0.10              # Alpha atteso vs benchmark
)
```

**Pesi (parametrizzabili in config):**
- `momentum: 0.40` → Trend è il fattore principale
- `risk_scalar: 0.30` → Convinzione risk-adjusted
- `volatility: 0.20` → Stabilità (inverso volatilità)
- `alpha: 0.10` → Alpha atteso (se disponibile)

**Output:**
- Lista candidati ordinata per `candidate_score` decrescente
- Top-N candidati selezionati (dove N dipende da cash e constraints)

### 3.3 Portfolio Constraints

#### A. Max Open Positions
```python
max_open_positions = config.get('max_open_positions', 3)  # Retail: max 3 posizioni

if current_open_positions >= max_open_positions:
    → Skip nuovi entry
    → Considera solo rebalancing posizioni esistenti
```

**Razionale:** Retail investor con portfolio €20-30k → max 3 posizioni per diversificazione senza over-diversification.

#### B. Cash Reserve
```python
min_cash_reserve_pct = config.get('min_cash_reserve_pct', 0.10)  # 10% cash minimo

available_cash = total_cash - (portfolio_value * min_cash_reserve_pct)

if available_cash < min_trade_value:
    → Skip nuovi entry
    → Attendi exit per liberare cash
```

**Razionale:** Mantenere sempre 10% cash per:
- Emergenze / opportunità
- Evitare fully invested (cash gating)
- Margine di sicurezza operativo

#### C. Position Overlap Check
```python
if symbol in current_positions:
    # Già abbiamo questa posizione
    position = current_positions[symbol]
    
    if position.days_held < position.expected_holding_days * 0.5:
        → Skip (troppo presto per aggiungere)
    
    elif candidate_score > position.entry_score * 1.2:
        → Considera ADD (scenario migliorato +20%)
    
    else:
        → Skip (scenario non abbastanza migliorato)
else:
    # Nuova posizione
    if candidate_score >= score_entry_min:
        → Entry (se cash disponibile)
```

**Razionale:**
- Non aggiungere a posizione appena aperta (evita averaging down immediato)
- Aggiungere solo se scenario migliorato significativamente (+20% score)
- Altrimenti, preferire nuove opportunità (diversificazione)

### 3.4 Capital Allocation

**Formula (per ogni candidato selezionato):**
```python
# Target weight basato su risk_scalar
target_weight = base_weight * risk_scalar  # es. 0.33 * 0.8 = 0.264

# Target value
target_value = portfolio_value * target_weight

# Qty (con rounding)
qty = int(target_value / price)

# Constraint: non superare cash disponibile
if qty * price > available_cash:
    qty = int(available_cash / price)  # Usa tutto il cash disponibile
```

**Parametri:**
- `base_weight = 1 / max_open_positions` (es. 1/3 = 0.33 per 3 posizioni max)
- `risk_scalar` → modula il peso (alta convinzione → peso pieno)

---

## 4. WORKFLOW OPERATIVO COMPLETO

### 4.1 Daily Workflow (Strategy Engine)

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: IDENTIFICA CANDIDATI                                │
└─────────────────────────────────────────────────────────────┘
candidates = [symbol for symbol in universe if signal_state[symbol] == 'RISK_ON']

┌─────────────────────────────────────────────────────────────┐
│ STEP 2: RANKING CANDIDATI                                   │
└─────────────────────────────────────────────────────────────┘
for symbol in candidates:
    candidate_score[symbol] = calculate_candidate_score(symbol)

ranked_candidates = sorted(candidates, key=lambda s: candidate_score[s], reverse=True)

┌─────────────────────────────────────────────────────────────┐
│ STEP 3: FILTRA PER CONSTRAINTS                              │
└─────────────────────────────────────────────────────────────┘
# A. Max positions
if len(current_positions) >= max_open_positions:
    ranked_candidates = []  # Skip tutti i nuovi entry

# B. Cash reserve
available_cash = calculate_available_cash()
if available_cash < min_trade_value:
    ranked_candidates = []  # Skip tutti i nuovi entry

# C. Overlap check
final_candidates = []
for symbol in ranked_candidates:
    if symbol not in current_positions:
        final_candidates.append(symbol)  # Nuova posizione OK
    elif should_add_to_position(symbol):
        final_candidates.append(symbol)  # ADD OK
    # else: skip (overlap non giustificato)

┌─────────────────────────────────────────────────────────────┐
│ STEP 4: ALLOCAZIONE CAPITALE                                │
└─────────────────────────────────────────────────────────────┘
for symbol in final_candidates:
    if available_cash < min_trade_value:
        break  # Esaurito cash
    
    # Calcola holding period dinamico
    expected_holding_days = calculate_expected_holding_days(
        risk_scalar[symbol],
        volatility[symbol],
        momentum_score[symbol]
    )
    
    # Calcola qty
    qty = calculate_qty(symbol, available_cash, risk_scalar[symbol])
    
    if qty > 0:
        propose_order(
            symbol=symbol,
            type='BUY',
            qty=qty,
            entry_score=candidate_score[symbol],
            expected_holding_days=expected_holding_days
        )
        available_cash -= qty * price[symbol]

┌─────────────────────────────────────────────────────────────┐
│ STEP 5: RIESAME POSIZIONI ESISTENTI                         │
└─────────────────────────────────────────────────────────────┘
for position in current_positions:
    days_held = current_date - position.entry_date
    
    # A. Riesame holding period
    if days_held >= position.expected_holding_days:
        if should_extend_holding(position):
            extend_holding(position)  # Calcola nuovo holding, aggiorna expected_exit_date
        else:
            propose_order(symbol=position.symbol, type='SELL', qty=position.qty, reason='EXIT_PLANNED')
    
    # B. Exit anticipato (stop-loss)
    elif stop_loss_triggered(position):
        propose_order(symbol=position.symbol, type='SELL', qty=position.qty, reason='EXIT_STOP_LOSS')
    
    # C. Exit anticipato (RISK_OFF)
    elif signal_state[position.symbol] == 'RISK_OFF':
        propose_order(symbol=position.symbol, type='SELL', qty=position.qty, reason='EXIT_RISK_OFF')
```

### 4.2 Esempio Concreto (Multi-Candidato)

**Situazione iniziale:**
- Portfolio value: €20,000
- Cash disponibile: €5,000 (dopo reserve 10%)
- Posizioni aperte: CSSPX.MI (entry 30gg fa, holding atteso 90gg, entry_score 0.72)
- Segnali RISK_ON oggi: CSSPX.MI, XS2L.MI, EIMI.MI

**STEP 1: Identifica candidati**
```
candidates = ['CSSPX.MI', 'XS2L.MI', 'EIMI.MI']
```

**STEP 2: Ranking**
```
candidate_score['XS2L.MI'] = 0.82   (momentum 0.8, risk_scalar 0.9, vol 15%, alpha 0.05)
candidate_score['EIMI.MI'] = 0.75   (momentum 0.7, risk_scalar 0.8, vol 18%, alpha 0.03)
candidate_score['CSSPX.MI'] = 0.68  (momentum 0.6, risk_scalar 0.7, vol 16%, alpha 0.02)

ranked_candidates = ['XS2L.MI', 'EIMI.MI', 'CSSPX.MI']
```

**STEP 3: Filtra per constraints**
```
# Max positions: 1 aperta < 3 max → OK
# Cash reserve: €5,000 > min_trade_value (€2,000) → OK
# Overlap check:
  - XS2L.MI: non in portafoglio → OK
  - EIMI.MI: non in portafoglio → OK
  - CSSPX.MI: in portafoglio, days_held=30 < 45 (50% di 90) → SKIP

final_candidates = ['XS2L.MI', 'EIMI.MI']
```

**STEP 4: Allocazione capitale**
```
1. XS2L.MI:
   - expected_holding_days = 90 * 1.0 * 0.85 * 0.94 = 72 giorni
   - target_value = 20000 * 0.33 * 0.9 = €5,940
   - qty = int(5940 / 236) = 25
   - Constraint: 25 * 236 = €5,900 > €5,000 available
   → qty = int(5000 / 236) = 21
   → BUY XS2L.MI qty=21 (€4,956)
   → Cash residuo: €5,000 - €4,956 = €44

2. EIMI.MI:
   - Cash residuo €44 < min_trade_value (€2,000)
   → SKIP (cash insufficiente)
```

**STEP 5: Riesame posizioni esistenti**
```
CSSPX.MI:
  - days_held = 30 < expected_holding_days (90) → HOLD
  - No stop-loss trigger → HOLD
  - signal_state = RISK_ON → HOLD
  → Nessuna azione
```

**Risultato finale:**
- **1 nuovo entry:** XS2L.MI (21 qty, holding atteso 72gg)
- **1 posizione mantenuta:** CSSPX.MI (in holding, 60gg rimanenti)
- **Cash residuo:** €44 (sotto soglia, attende prossimo exit)

---

## 5. SCHEMA DATABASE

### 5.1 Modifiche fiscal_ledger

**Nuove colonne:**
```sql
ALTER TABLE fiscal_ledger ADD COLUMN entry_date DATE;
ALTER TABLE fiscal_ledger ADD COLUMN entry_score REAL;
ALTER TABLE fiscal_ledger ADD COLUMN expected_holding_days INTEGER;
ALTER TABLE fiscal_ledger ADD COLUMN expected_exit_date DATE;
ALTER TABLE fiscal_ledger ADD COLUMN actual_holding_days INTEGER;
ALTER TABLE fiscal_ledger ADD COLUMN exit_reason VARCHAR;
```

**Descrizione colonne:**
- `entry_date`: Data entry (per calcolare days_held)
- `entry_score`: Candidate score all'entry (per confronto in riesame)
- `expected_holding_days`: Holding calcolato all'entry
- `expected_exit_date`: Data exit pianificato (entry_date + expected_holding_days)
- `actual_holding_days`: Holding effettivo (calcolato all'exit)
- `exit_reason`: Motivo exit ('EXIT_PLANNED', 'EXIT_RISK_OFF', 'EXIT_STOP_LOSS', 'HOLDING_EXTENDED')

### 5.2 Esempio Record

**Entry (BUY):**
```
date: 2025-06-27
symbol: XS2L.MI
type: BUY
qty: 21
price: 236.00
entry_date: 2025-06-27
entry_score: 0.82
expected_holding_days: 72
expected_exit_date: 2025-09-07
actual_holding_days: NULL
exit_reason: NULL
```

**Exit (SELL pianificato):**
```
date: 2025-09-07
symbol: XS2L.MI
type: SELL
qty: 21
price: 245.00
entry_date: 2025-06-27
entry_score: 0.82
expected_holding_days: 72
expected_exit_date: 2025-09-07
actual_holding_days: 72
exit_reason: 'EXIT_PLANNED'
```

**Exit (SELL anticipato per RISK_OFF):**
```
date: 2025-08-15
symbol: XS2L.MI
type: SELL
qty: 21
price: 230.00
entry_date: 2025-06-27
entry_score: 0.82
expected_holding_days: 72
expected_exit_date: 2025-09-07
actual_holding_days: 49
exit_reason: 'EXIT_RISK_OFF'
```

---

## 6. CONFIGURAZIONE

### 6.1 Config File (etf_universe.json)

```json
{
  "portfolio_construction": {
    "max_open_positions": 3,
    "min_cash_reserve_pct": 0.10,
    "min_trade_value": 2000,
    "score_entry_min": 0.70,
    "score_add_threshold": 1.2
  },
  "holding_period": {
    "base_holding_days": 90,
    "min_holding_days": 30,
    "max_holding_days": 180
  },
  "ranking_weights": {
    "momentum": 0.40,
    "risk_scalar": 0.30,
    "volatility": 0.20,
    "alpha": 0.10
  }
}
```

### 6.2 Parametri Descrizione

**portfolio_construction:**
- `max_open_positions`: Numero massimo posizioni aperte contemporaneamente (retail: 3)
- `min_cash_reserve_pct`: Cash reserve minimo % portfolio (retail: 10%)
- `min_trade_value`: Valore minimo trade in EUR (evita micro-operazioni)
- `score_entry_min`: Score minimo per entry (filtro qualità)
- `score_add_threshold`: Soglia miglioramento score per ADD a posizione esistente (es. 1.2 = +20%)

**holding_period:**
- `base_holding_days`: Holding base (default 90 giorni = 3 mesi)
- `min_holding_days`: Holding minimo (evita overtrading)
- `max_holding_days`: Holding massimo (evita posizioni "dimenticate")

**ranking_weights:**
- `momentum`: Peso trend strength nel candidate score
- `risk_scalar`: Peso risk-adjusted conviction
- `volatility`: Peso stabilità (inverso volatilità)
- `alpha`: Peso alpha atteso vs benchmark

---

## 7. IMPATTO ATTESO

### 7.1 Execution Rate

**Attuale (senza holding period):**
- 279 RISK_ON / 251 giorni
- 9 ordini eseguiti
- Execution rate: 3.59%
- Problema: portfolio fully invested, nessun exit pianificato

**Atteso (con holding period dinamico):**
- Media holding: ~60 giorni (distribuzione 30-120gg)
- Con 3 posizioni max: ~1.5 exit/mese (60gg / 3 posizioni ≈ 1 ogni 20gg)
- Ogni exit libera cash → nuovi entry possibili
- **Execution rate atteso: 12-18%** (3-4x miglioramento)

### 7.2 Cash Rotation

**Attuale:**
- Cash medio: €-15,259 (negativo = fully invested)
- Cash min: €-19,844
- Cash max: €-1,908
- Problema: sempre fully invested, nessuna liquidità

**Atteso:**
- Cash reserve: 10% portfolio (€2,000 su €20k)
- Exit pianificati liberano cash regolarmente
- Cash disponibile per nuovi entry: €3,000-5,000 (media)
- **Cash gating: eliminato**

### 7.3 Performance

**Miglioramenti attesi:**
- **Riduzione "buy and hold involontario"**: exit pianificati evitano posizioni stagnanti
- **Migliore capital allocation**: ranking candidati → focus su migliori opportunità
- **Disciplina operativa**: riesame periodico → adattamento a scenari mutevoli
- **Turnover controllato**: holding min 30gg evita overtrading

**Rischi:**
- **Aumento turnover**: più exit → più commissioni (mitigato da holding min 30gg)
- **Timing risk**: exit pianificato potrebbe essere sub-ottimale (mitigato da riesame scenario)

---

## 8. IMPLEMENTAZIONE

### 8.1 Componenti da Modificare

1. **Schema DB** (`scripts/db/setup_db.py`)
   - Aggiungere colonne a `fiscal_ledger`

2. **Strategy Engine** (`scripts/strategy/strategy_engine.py`)
   - Funzione `calculate_expected_holding_days()`
   - Funzione `calculate_candidate_score()`
   - Funzione `rank_candidates()`
   - Funzione `filter_by_constraints()`
   - Funzione `should_add_to_position()`
   - Funzione `should_extend_holding()`
   - Workflow completo (5 step)

3. **Config** (`config/etf_universe.json`)
   - Sezioni `portfolio_construction`, `holding_period`, `ranking_weights`

4. **Backtest Engine** (`scripts/backtest/backtest_engine.py`)
   - Integrazione nuove colonne fiscal_ledger
   - Supporto exit_reason logging

5. **Execute Orders** (`scripts/trading/execute_orders.py`)
   - Passaggio parametri entry_score, expected_holding_days all'insert ledger

### 8.2 Test Plan

1. **Unit test:** Funzioni calcolo holding, candidate score, ranking
2. **Integration test:** Workflow completo strategy engine
3. **Backtest:** Run completo periodo 2025-01-05 → 2026-01-05
4. **Validation:** Verifica execution rate, cash rotation, performance vs benchmark

---

## 9. DOMANDE APERTE / DECISIONI

### 9.1 Parametri da Validare

- [ ] `base_holding_days = 90` → OK o preferisci 60/120?
- [ ] `min_cash_reserve_pct = 0.10` → OK o preferisci 5%/15%?
- [ ] `max_open_positions = 3` → OK o preferisci 2/4?
- [ ] Pesi ranking (momentum 0.4, risk 0.3, vol 0.2, alpha 0.1) → OK o modifiche?

### 9.2 Logica da Confermare

- [ ] Riesame scenario: se favorevole, estendere holding di quanto? (proposta: ricalcola holding dinamico con condizioni aggiornate)
- [ ] ADD a posizione esistente: soglia +20% score OK o preferisci +30%/+50%?
- [ ] Exit anticipato: solo RISK_OFF + stop-loss o anche altri trigger (es. drawdown portfolio)?

### 9.3 Edge Cases

- [ ] Cosa fare se tutti i candidati hanno score < score_entry_min? (proposta: skip entry, attendi scenario migliore)
- [ ] Cosa fare se riesame scenario indica "estendi" ma portfolio è già a max positions? (proposta: estendi comunque, non è un nuovo entry)
- [ ] Cosa fare se exit pianificato cade in giorno festivo? (proposta: primo giorno lavorativo successivo)

---

## 10. NEXT STEPS

1. **Revisione documento** con utente
2. **Validazione parametri** e logica
3. **Implementazione** (schema + strategy engine + config)
4. **Test** (unit + integration + backtest)
5. **Analisi risultati** (execution rate, performance, cash rotation)
6. **Iterazione** (tuning parametri se necessario)

---

**Fine Design Document**
