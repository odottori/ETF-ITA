# Guardrails Bug Fixes Summary

## Bug Critici Risolti

### 1. NameError: `guardrails` vs `guardrails_status`
**Problema**: Il codice usava `guardrails[...]` invece di `guardrails_status[...]` in più punti.
**Impatto**: Causava `NameError` quando si attivavano raccomandazioni (SPY guard, concentration).
**Correzione**: Sostituite tutte le occorrenze di `guardrails[...]` con `guardrails_status[...]`.

**Righe corrette**:
- Linea 92: SPY guard recommendation
- Linea 104: SPY guard RISK_ON check  
- Linea 157: Concentration recommendation
- Linea 209: Signal changes recommendation

### 2. Coerenza Prezzi di Valorizzazione
**Problema**: La concentrazione e market value usavano prezzi non coerenti (trade price o adj_close).
**Impatto**: KPI di concentrazione inaffidabili e non conformi DIPF.
**Correzione**: Implementata query che usa prezzi di chiusura correnti da `market_data`.

**Nuova query**:
```sql
WITH current_prices AS (
    SELECT symbol, close as current_price
    FROM market_data 
    WHERE date = (SELECT MAX(date) FROM market_data)
),
position_summary AS (
    SELECT 
        fl.symbol,
        SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) as qty,
        cp.current_price,
        SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) * cp.current_price as market_value
    FROM fiscal_ledger fl
    JOIN current_prices cp ON fl.symbol = cp.symbol
    WHERE fl.type IN ('BUY', 'SELL')
    GROUP BY fl.symbol, cp.current_price
    HAVING SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) != 0
)
SELECT symbol, qty, current_price, market_value
FROM position_summary
```

### 3. Correzione Indici Array
**Problema**: Il codice usava `pos[2]` per market value, ma dopo la correzione è `pos[3]`.
**Correzione**: Aggiornati tutti i riferimenti per usare la struttura corretta:
- `total_value = sum(pos[3] for pos in positions)`  
- `max_concentration = max(pos[3] / total_value ...)`

## Verifica

✅ **NameError risolto**: Nessuna occorrenza di `guardrails[` rimasta
✅ **Prezzi coerenti**: Query usa `close` da `market_data` per valorizzazione
✅ **Struttura dati**: Indici array correttamente allineati

## Test Creati

- `tests/test_guardrails_fixes.py`: Verifica automatica delle correzioni
- Test copre: NameError fix, query prezzi close, coerenza calcoli

## Conformità DIPF

Le correzioni assicurano conformità con:
- **DIPF §7.2.1**: Prezzi di chiusura per valorizzazione portfolio
- **DIPF §4.3**: Coerenza segnali (adj_close) vs valorizzazione (close)
- **DIPF §6.1**: Robustezza risk management e guardrails

Il sistema ora ha guardrails Production Ready con KPI affidabili e coerenti.
