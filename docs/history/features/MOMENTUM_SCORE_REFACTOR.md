# Momentum Score Refactor - ETF-ITA v10.7.8

## Problema Risolto

L'`expected_alpha` era un placeholder con valori monetari irrealistici (€1-3 per €10k) che rendevano la logica `alpha > costs` quasi inutile e introducevano rischio di turnover eccessivo.

## Soluzione Implementata

### 1. Rinomina Campi
- `expected_alpha_est` → `momentum_score` (score 0-1)
- `do_nothing_score` → `trade_score` (score 0-1)
- `total_expected_alpha` → `total_momentum_score` (media score)

### 2. Logica MANDATORY vs OPPORTUNISTIC

#### MANDATORY (sempre eseguiti)
- Stop-loss triggers
- Force rebalancing (deviation > force_deviation)
- Segnali RISK_ON/OFF forti

#### OPPORTUNISTIC (solo se score sufficiente)
- Rebalancing: `trade_score >= score_rebalance_min`
- Entry nuove posizioni: `momentum_score >= score_entry_min`

### 3. Configurazione Soglie

```json
"settings": {
  "score_entry_min": 0.7,      # Minimo per nuove posizioni
  "score_rebalance_min": 0.6,  # Minimo per rebalancing
  "force_deviation": 0.05      # Soglia force rebalancing
}
```

### 4. Score Calculation

#### Momentum Score (0-1)
```python
base_momentum = 0.5
momentum_score = base_momentum * risk_scalar
vol_adjustment = min(1.5, 0.10 / current_vol)
momentum_score = min(1.0, momentum_score * vol_adjustment)
```

#### Trade Score (0-1)
```python
cost_ratio = (commission + slippage + tax_estimate) / position_value
trade_score = momentum_score - cost_ratio * 10  # Scaling costi
trade_score = max(0, min(1, trade_score))  # Clamp 0-1
```

## Correzioni Aggiuntive

### avg_price → avg_buy_price
Corretti tutti i riferimenti da `avg_price` a `avg_buy_price` per coerenza con schema DB.

## Test Verificati

1. **test_momentum_score_fix.py**: 6/6 test passati
   - Logica MANDATORY vs OPPORTUNISTIC
   - Score calculation range 0-1
   - Threshold behavior

2. **test_strategy_engine_logic.py**: 5/5 test passati
   - Chiave avg_buy_price corretta
   - Position caps non violati
   - Logica trade_score separata
   - Momentum score modellistico
   - Logica unificata rebalancing/segnali

3. **test_execute_orders_bridge.py**: Campi aggiornati
   - `momentum_score` invece di `expected_alpha_est`
   - `trade_score` invece di `do_nothing_score`

## Risultati

- ✅ Score realistici e difendibili (0-1 scale)
- ✅ Separazione chiara MANDATORY vs OPPORTUNISTIC
- ✅ Threshold configurabili per tuning
- ✅ Nessun rischio turnover eccessivo
- ✅ Coerenza schema DB (avg_buy_price)
- ✅ Test coverage completa

## File Modificati

- `scripts/core/strategy_engine.py` - Logica principale
- `config/etf_universe.json` - Soglie configurazione
- `tests/test_execute_orders_bridge.py` - Test bridge
- `tests/test_strategy_engine_logic.py` - Test logica
- `tests/test_strategy_engine_fixes.py` - Test fixes

## Next Steps

Il sistema ora usa score euristici robusti invece di expected return monetari, eliminando il rischio di decisioni basate su stime irrealistiche e mantenendo la flessibilità operativa.
