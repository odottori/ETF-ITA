# Closed Loop Trading Architecture - ETF Italia Project v10

## Problema Risolto

Il sistema ETF-ITA v10 aveva un buco critico nell'architettura: mancava il bridge che trasforma gli ordini generati in movimenti effettivi nel ledger fiscale. Il sistema era quindi più simile a un generatore di raccomandazioni che a un sistema di trading completo.

## Architettura Corretta

### Flusso Operativo Completo (Closed Loop)

```
compute_signals.py → strategy_engine.py → execute_orders.py → fiscal_ledger
       ↓                    ↓                    ↓              ↓
   signals table      orders JSON file     ledger records  portfolio value
```

### Componenti Principali

#### 1. compute_signals.py (ESISTENTE)
- Genera segnali oggettivi (RISK_ON/RISK_OFF/HOLD)
- Calcola risk scalar basato su volatilità e drawdown
- Salva nella tabella `signals`

#### 2. strategy_engine.py (MODIFICATO)
- Legge segnali da tabella `signals`
- Calcola target weights e determina rebalancing
- Genera ordini realistici con costi e tax friction
- **NUOVO**: Flag `--commit` ora funzionale e integrato
- Salva ordini in `data/orders/orders_*.json`

#### 3. execute_orders.py (NUOVO)
- **Bridge critico** tra ordini e ledger
- Legge file ordini JSON
- Valida eseguibilità (posizioni sufficienti per vendite)
- Calcola costi realistici (commissioni, slippage, tax)
- Scrive record BUY/SELL in `fiscal_ledger`
- Registra audit trail in `trade_journal`
- Supporta modalità dry-run e commit

#### 4. update_ledger.py (ESISTENTE)
- Calcola cash interest mensile
- Sanity check bloccanti
- Aggiorna PMC snapshot
- Report posizioni correnti

#### 5. run_complete_cycle.py (NUOVO)
- Orchestrazione dell'intero ciclo
- Esegue: signals → strategy → execute → ledger
- Supporta modalità dry-run e commit
- Report finale con stato sistema

## Utilizzo

### Dry Run (test senza modifiche)
```bash
python scripts/core/run_complete_cycle.py
```

### Commit Mode (esecuzione reale)
```bash
python scripts/core/run_complete_cycle.py --commit
```

### Status Sistema
```bash
python scripts/core/run_complete_cycle.py --status
```

### Esecuzione Manuale Componenti
```bash
# Solo segnali
python scripts/core/compute_signals.py

# Solo strategia (dry-run)
python scripts/core/strategy_engine.py --dry-run

# Solo strategia (con commit)
python scripts/core/strategy_engine.py --commit

# Solo esecuzione ordini
python scripts/core/execute_orders.py --orders-file data/orders/orders_20240106_120000.json --commit

# Solo aggiornamento ledger
python scripts/core/update_ledger.py --commit
```

## Dettagli Implementazione

### execute_orders.py - Bridge Critico

#### Funzionalità Chiave
1. **Validazione Ordini**: Verifica integrità file e struttura ordini
2. **Controllo Posizioni**: Verifica disponibilità per vendite
3. **Calcolo Costi Realistici**:
   - Commissioni: % o minimo €5
   - Slippage: dinamico basato su volatilità
   - Tax: 26% su realized gains
4. **Arrotondamenti Finanziari**: Decimal precise per importi
5. **Audit Trail**: Registrazione completa in `trade_journal`
6. **Transazioni ACID**: Rollback su errori

#### Esempio Record Generato
```sql
INSERT INTO fiscal_ledger 
(id, date, type, symbol, qty, price, fees, tax_paid, run_id)
VALUES (123, '2024-01-06', 'BUY', 'IE00B4L5Y983', 75.0, 45.0, 3.38, 0.0, 'execute_orders_20240106_120000')
```

### strategy_engine.py - Integrazione Commit

#### Modifiche Principali
1. **Parametro commit**: Funzione ora accetta `commit=False`
2. **Salva sempre ordini**: File creato sia in dry-run che commit
3. **Esecuzione condizionale**: Se `commit=True`, chiama `execute_orders()`
4. **Error handling**: Propaga errori da execute_orders

### trade_journal - Audit Trail

#### Struttura
```sql
CREATE TABLE trade_journal (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    signal_state VARCHAR NOT NULL,
    risk_scalar DOUBLE,
    explain_code VARCHAR,
    flag_override BOOLEAN DEFAULT FALSE,
    override_reason VARCHAR,
    theoretical_price DOUBLE,
    realized_price DOUBLE,
    slippage_bps DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### Utilità
- Tracking decisioni operative
- Analisi performance vs segnali
- Debug discrepanze
- Compliance audit

## Test

### test_execute_orders_bridge.py
Test completo del bridge con:
- Setup database temporaneo
- Ordini di test realistici
- Verifica dry-run vs commit
- Edge cases (posizioni insufficienti)
- Validazione costi e tax

### Esecuzione Test
```bash
python tests/test_execute_orders_bridge.py
```

## Sicurezza e Controllo

### Validazioni Pre-Esecuzione
1. **Integrità file ordini**: JSON structure validation
2. **Disponibilità posizioni**: Check qty sufficiente per vendite
3. **Coerenza prezzi**: Prezzi positivi e ragionevoli
4. **Limiti operativi**: No posizioni negative o cash negativo

### Transazioni ACID
- BEGIN TRANSACTION prima modifiche
- ROLLBACK su qualsiasi errore
- COMMIT solo dopo successo completo

### Audit Trail Completo
- Run ID univoco per ogni esecuzione
- Registro in `trade_journal` per ogni ordine
- Traceability da segnale a esecuzione

## Impatto Operativo

### Prima (Gap nell'architettura)
- compute_signals.py → signals table ✅
- strategy_engine.py → orders JSON ✅  
- **MANCA**: orders JSON → fiscal_ledger ❌
- update_ledger.py → cash interest ✅

### Dopo (Closed loop completo)
- compute_signals.py → signals table ✅
- strategy_engine.py → orders JSON ✅
- **NUOVO**: execute_orders.py → fiscal_ledger ✅
- update_ledger.py → cash interest ✅

### Risultato
Il sistema è ora un vero sistema di trading/backtest "chiuso" (closed loop) con:
- Catena di esecuzione completa
- Audit trail integrato
- Costi realistici
- Gestione fiscale corretta
- Sicurezza transazionale

## Next Steps

1. **Test su dati reali**: Eseguire ciclo completo con dati di produzione
2. **Performance monitoring**: Metriche su esecuzione ordini
3. **Enhanced reporting**: Report dettagliati su ogni ciclo
4. **Automation scheduling**: Cron job per esecuzione automatica
5. **Risk monitoring**: Alert su anomalie nell'esecuzione
