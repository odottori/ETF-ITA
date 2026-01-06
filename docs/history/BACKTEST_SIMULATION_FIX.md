# Backtest Simulation Fix - ETF Italia Project v10.7.2

## Problema Risolto: "Reporting senza Simulazione"

### Descrizione del Problema
Il sistema backtest originale calcolava KPI performance basati su `portfolio_overview`, ma questa vista:
1. **NON esisteva** nel database setup canonico
2. Era creata solo da script utility con dati artificiali (valori = 0)
3. **NON rifletteva** una vera simulazione di trading

**Conseguenza:** I KPI erano un "esercizio di stile" senza valore difendibile.

### Analisi Root Cause

#### File Coinvolti
- `scripts/core/backtest_runner.py` (righe 211-215): Usava `portfolio_overview` inesistente
- `scripts/utility/create_portfolio_simple.py`: Creava vista con dati artificiali
- `scripts/utility/create_portfolio_overview_fixed.py`: Tentativo di fix incompleto

#### Problemi Fundamentali
1. **Mancanza simulazione**: Nessuna esecuzione ordini reali
2. **Dati statici**: KPI basati su prezzi raw di market_data
3. **Nessuna contabilizzazione**: Fiscal_ledger non aggiornato
4. **Performance artifattuale**: Return basati su adj_close, non su portfolio value

### Soluzione Implementata

#### 1. Backtest Engine (`scripts/core/backtest_engine.py`)
Nuovo motore di simulazione completo con:

- **Inizializzazione portfolio**: Deposito capitale iniziale in fiscal_ledger
- **Generazione segnali**: Calcolo RISK_ON/RISK_OFF basato su trend/momentum
- **Esecuzione ordini**: BUY/SELL con costi realistici (commission + slippage)
- **Contabilizzazione fiscale**: Integrata con logica tax_loss_carryforward
- **Portfolio overview**: Creata da dati reali di simulazione

#### 2. Integrazione in Backtest Runner
Modificato `backtest_runner.py` per:
- Eseguire simulazione reale PRIMA del calcolo KPI
- Garantire `portfolio_overview` basata su dati di trading
- Mantenere compatibilità con Run Package esistente

### Flusso Corretto

```
1. backtest_engine.py
   └─ Inizializza portfolio (€20,000)
   └─ Calcola segnali (RISK_ON/OFF)
   └─ Genera ordini (BUY/SELL)
   └─ Esegue ordini (+ costi + tasse)
   └─ Aggiorna fiscal_ledger
   └─ Crea portfolio_overview (dati reali)

2. backtest_runner.py
   └─ Calcola KPI da portfolio_overview reale
   └─ Genera Run Package con performance difendibile
```

### KPI Ora Difendibili

#### Prima (Artifattuali)
- CAGR basato su prezzi raw
- Drawdown teorico su adj_close
- Sharpe ratio non rappresentativo

#### Dopo (Realistici)
- **CAGR**: Basato su valore portfolio reale (initial → final)
- **Drawdown**: Calcolato su equity curve reale
- **Sharpe**: Risk-adjusted return su volatilità reale
- **Turnover**: Basato su ordini effettivamente eseguiti

### Dettagli Tecnici

#### Esecuzione Ordini
```python
# BUY: costi realistici
total_cost = qty * price + commission + slippage

# SELL: calcolo fiscale completo
proceeds = qty * price - commission - slippage
cost_basis = qty * avg_cost  # FIFO
gain = proceeds - cost_basis
tax = gain * 0.26 if gain > 0 else 0
```

#### Portfolio Value
```python
# Valore giornaliero reale
market_value = Σ(position_qty * current_price)
cash = Σ(fiscal_ledger cash flows)
portfolio_value = market_value + cash
```

### Validazione

#### Test di Integrazione
1. **Sanity Check**: Posizioni negative, cash negativo, PMC coerenti
2. **Coerenza Dati**: portfolio_overview ↔ fiscal_ledger
3. **Performance Realistica**: KPI confrontabili con broker statement

#### Risultati Attesi
- KPI difendibili per audit
- Coerenza con rendicontazione fiscale
- Tracciabilità completa ordine → performance

### Impatto sul Sistema

#### Files Modificati
- ✅ `scripts/core/backtest_engine.py` (NUOVO)
- ✅ `scripts/core/backtest_runner.py` (INTEGRATO)

#### Files Non Modificati
- `scripts/core/execute_orders.py` (rimane per trading live)
- `scripts/core/strategy_engine.py` (segnali per live trading)
- `scripts/core/setup_db.py` (schema canonico invariato)

### Compatibilità

#### Backward Compatibility
- Run Package format invariato
- KPI structure identica (ma con valori reali)
- Integration con sequence_runner mantenuta

#### Forward Compatibility
- Facile estensione per multi-period backtest
- Supporto per walk-forward analysis
- Integrabile con Monte Carlo stress testing

## Conclusione

**Problema risolto:** Il sistema ora genera KPI basati su simulazione reale, non più su dati artificiali.

**Risultato:** Performance misurabile in modo difendibile, coerente con:
- DIPF §7.2.1 (benchmark rules)
- Fiscalità italiana (PMC, zainetto)
- Best practices retail trading

**Stato:** Production Ready per backtest con simulazione reale.

---

*Documentazione aggiornata: 2026-01-06*
*Versione: v10.7.2*
