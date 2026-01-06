# Trailing Stop V2 Implementation - ETF Italia Project v10.7.4

## Problema Risolto

Il "trailing stop" implementato in `implement_risk_controls.py` non era realmente trailing:
- Calcolava PnL vs `avg_buy_price` (statico)
- Il "trailing" era solo un secondo stop-loss più stretto (-10% vs -15%)
- Non seguiva il massimo favorevole post-entry

## Soluzione Implementata

### 1. Architettura Peak Tracking

**Nuova tabella `position_peaks`:**
```sql
CREATE TABLE position_peaks (
    symbol VARCHAR,
    entry_date DATE,
    peak_price DECIMAL(10,4),
    peak_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (symbol, entry_date)
);
```

**Logica trailing stop vero:**
- **Entry**: Registra peak_price = entry_price
- **Update**: Se current_price > peak_price → aggiorna peak
- **Stop**: Se `(current_price - peak_price) / peak_price <= -10%`

### 2. Configurazione

Aggiunto in `etf_universe.json`:
```json
"trailing_stop_v2": {
  "enabled": true,
  "drawdown_threshold": -0.10,
  "min_profit_activation": 0.05,
  "reset_on_close": true
}
```

### 3. Funzionalità Implementate

**File creati:**
- `scripts/core/trailing_stop_v2.py` - Core implementation
- `scripts/core/implement_risk_controls_v2.py` - Integration layer
- `tests/test_trailing_stop_v2.py` - Complete test suite

**Funzioni principali:**
- `initialize_position_peak()` - Inizializza peak per nuova posizione
- `update_position_peak()` - Aggiorna peak se superato
- `check_trailing_stop_v2()` - Verifica trailing stop vero
- `sync_position_peaks_from_ledger()` - Recupero dati storici

### 4. Test Results

✅ **Test superati:**
- Peak tracking automatico
- Aggiornamento peaks su nuovi massimi
- Calcolo drawdown da peak (non da entry)
- Trigger solo dopo profit minimo (+5%)
- Reset su chiusura posizione

**Scenario test:**
- Entry: €10.00
- Peak: €11.80 (+18%)
- Current: €10.00
- Drawdown da peak: -15.3%
- **Legacy**: No trigger (PnL: 0% vs entry)
- **V2**: TRIGGER (DD: -15.3% vs peak)

## Differenze Chiave

| Aspetto | Legacy | V2 (Vero) |
|---------|--------|-----------|
| Riferimento | avg_buy_price | peak_price |
| Comportamento | Statico | Dinamico |
| Trigger | -10% vs entry | -10% vs peak |
| Attivazione | Immediata | Dopo +5% profit |
| Protezione | Limitata | Completa |

## Integrazione

Il sistema mantiene retrocompatibilità:
- Se `trailing_stop_v2.enabled = false` → usa legacy
- Se `true` → usa trailing stop vero
- Configurazione per singolo symbol possibile

## Prossimi Passi

1. Abilitare in produzione impostando `enabled: true`
2. Monitorare trigger in dry-run per validazione
3. Estendere ad altri symbol se necessario
4. Integrare con strategy engine per update automatici

**Risultato: Trailing stop finalmente vero e corretto.**
