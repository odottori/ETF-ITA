# SCHEMA CONTRACT - ETF Italia Project v003
# Documento vincolante per coerenza schema database

## # PRINCIPI FONDAMENTALI
1. **Single Source of Truth**: Questo documento è l'unica fonte veritabile per schema DB
2. **Breaking Changes Only**: Modifiche solo con revisione formale e test
3. **Version Control**: Ogni modifica incrementa versione e aggiorna changelog
4. **Test Coverage**: Tutte le tabelle devono avere test di coerenza

## # CHANGELOG
- **v003** - Riorganizzazione docs e allineamento canonici 003
- **v10.7.7** - Aggiunto ID Helper con range ID separati per ambiente (Production: 1-9999, Backtest: 50000-59999)
- **v10.7.6** - Pre-trade controls implementati con reject logging strutturato
- **v10.7.5** - Schema contract baseline vincolante con gate bloccante
- **v10.7.3** - Versione iniziale del contract

## # TABELLE CORE

### market_data
```sql
CREATE TABLE market_data (
    symbol VARCHAR NOT NULL,
    date DATE NOT NULL,
    adj_close DOUBLE CHECK (adj_close > 0),
    close DOUBLE CHECK (close > 0),
    high DOUBLE CHECK (high >= 0),
    low DOUBLE CHECK (low >= 0),
    volume BIGINT CHECK (volume >= 0),
    source VARCHAR DEFAULT 'YF',
    PRIMARY KEY (symbol, date),
    CHECK (high >= low),
    CHECK (high >= close),
    CHECK (low <= close)
)
```

### fiscal_ledger
```sql
CREATE TABLE fiscal_ledger (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    type VARCHAR NOT NULL CHECK (type IN ('DEPOSIT', 'BUY', 'SELL', 'INTEREST')),
    symbol VARCHAR NOT NULL,
    qty DOUBLE NOT NULL,
    price DOUBLE NOT NULL CHECK (price >= 0),
    fees DOUBLE DEFAULT 0.0 CHECK (fees >= 0),
    tax_paid DOUBLE DEFAULT 0.0 CHECK (tax_paid >= 0),
    pmc_snapshot DOUBLE,
    trade_currency VARCHAR DEFAULT 'EUR',
    exchange_rate_used DOUBLE DEFAULT 1.0 CHECK (exchange_rate_used > 0),
    price_eur DOUBLE,
    run_id VARCHAR,
    run_type VARCHAR DEFAULT 'PRODUCTION',
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### signals
```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    signal_state VARCHAR NOT NULL CHECK (signal_state IN ('RISK_ON', 'RISK_OFF', 'HOLD')),
    risk_scalar DOUBLE CHECK (risk_scalar >= 0 AND risk_scalar <= 1),
    explain_code VARCHAR,
    sma_200 DOUBLE,
    volatility_20d DOUBLE,
    spy_guard BOOLEAN DEFAULT FALSE,
    regime_filter VARCHAR DEFAULT 'NEUTRAL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, symbol)
)
```

### orders
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    order_type VARCHAR NOT NULL CHECK (order_type IN ('BUY', 'SELL', 'HOLD')),
    qty DOUBLE NOT NULL,
    price DOUBLE NOT NULL CHECK (price >= 0),
    status VARCHAR DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'EXECUTED', 'CANCELLED')),
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## # VISTE ANALYTICS

### portfolio_summary
```sql
CREATE VIEW portfolio_summary AS
WITH current_positions AS (
    SELECT 
        symbol,
        SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
        AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price
    FROM fiscal_ledger 
    WHERE type IN ('BUY', 'SELL')
    GROUP BY symbol
    HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
),
cash_balance AS (
    SELECT COALESCE(SUM(CASE 
        WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
        WHEN type = 'SELL' THEN qty * price - fees - tax_paid
        WHEN type = 'BUY' THEN -(qty * price + fees)
        WHEN type = 'INTEREST' THEN qty
        ELSE 0 
    END), 0) as cash
    FROM fiscal_ledger
)
SELECT 
    cp.symbol,
    cp.qty,
    cp.avg_buy_price,
    md.close as current_price,
    cp.qty * md.close as market_value,
    cb.cash,
    cb.cash + SUM(cp.qty * md.close) OVER () as total_portfolio_value
FROM current_positions cp
JOIN market_data md ON cp.symbol = md.symbol 
    AND md.date = (SELECT MAX(date) FROM market_data)
CROSS JOIN cash_balance cb
```

### risk_metrics
```sql
CREATE VIEW risk_metrics AS
WITH daily_returns AS (
    SELECT 
        symbol,
        date,
        adj_close,
        close,
        volume,
        CASE 
            WHEN LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) IS NOT NULL 
            THEN (adj_close - LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date)) / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date)
            ELSE NULL 
        END as daily_return
    FROM market_data
),
rolling_metrics AS (
    SELECT 
        symbol,
        date,
        adj_close,
        close,
        volume,
        daily_return,
        AVG(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma_200,
        MAX(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS UNBOUNDED PRECEDING) as high_water_mark
    FROM daily_returns
)
SELECT 
    symbol,
    date,
    adj_close,
    close,
    volume,
    sma_200,
    STDDEV_SAMP(daily_return) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) * SQRT(252) as volatility_20d,
    high_water_mark,
    (adj_close / high_water_mark - 1) as drawdown_pct,
    daily_return
FROM rolling_metrics
ORDER BY symbol, date
```

### execution_prices
```sql
CREATE VIEW execution_prices AS
SELECT 
    symbol,
    date,
    close as execution_price,
    volume,
    CASE 
        WHEN LAG(close) OVER (PARTITION BY symbol ORDER BY date) IS NOT NULL 
        THEN (close - LAG(close) OVER (PARTITION BY symbol ORDER BY date)) / LAG(close) OVER (PARTITION BY symbol ORDER BY date)
        ELSE NULL 
    END as daily_return
FROM market_data
ORDER BY symbol, date
```

## # CONVENZIONI VINCOLANTI

### 1. Prezzi
- **adj_close**: segnali (trend, momentum, risk metrics)
- **close**: esecuzione ordini, valorizzazione portfolio
- **execution_price**: alias per close in vista execution_prices

### 2. Date
- Sempre formato DATE (non DATETIME)
- timezone: UTC per market data, local per fiscal_ledger

### 3. Valute
- trade_currency: sempre 'EUR' per ETF Italia
- exchange_rate_used: 1.0 per operazioni EUR/EUR
- price_eur: NULL per operazioni EUR (redundant)

### 4. IDs
- Tutte le tabelle hanno id INTEGER PRIMARY KEY
- INSERT OR REPLACE deve includere id esplicito
- Usare next_id pattern per evitare conflitti

### 5. Run Tracking
- run_id: identificativo univoco per sessione
- run_type: 'PRODUCTION' | 'BACKTEST' | 'TEST'
- notes: campo libero per traceability

## # VALIDATION RULES

### Coerenza Cross-Table
1. **signals.date** deve esistere in **market_data.date** per ogni symbol
2. **fiscal_ledger.symbol** deve esistere in **market_data.symbol**
3. **portfolio_summary** usa solo **close** per valorizzazione
4. **risk_metrics** usa solo **adj_close** per calcoli

### Integrità Referenziale
1. **fiscal_ledger.type** solo valori ammessi
2. **signals.signal_state** solo valori ammessi
3. **orders.status** solo valori ammessi
4. Tutti i prezzi >= 0

### Business Rules
1. PMC snapshot aggiornato per ogni operazione
2. Tax paid calcolato su gain reali
3. Risk scalar sempre tra 0.0 e 1.0
4. Volume sempre >= 0

## # CHANGELOG

### v10.7.4 (2026-01-06)
- ✅ Aggiunto close e volume a vista risk_metrics per completezza dati
- ✅ Allineato SCHEMA_CONTRACT.md con modifiche setup_db.py

### v10.7.3 (2026-01-06)
- ✅ Aggiunto run_type e notes a fiscal_ledger
- ✅ Corretto INSERT signals per includere id esplicito
- ✅ Documentato schema contract completo

### v10.7.2 (2026-01-05)
- ✅ Aggiunto tax_loss_carryforward table
- ✅ Enhanced risk management integration

### v10.7.0 (2026-01-04)
- ✅ Separazione adj_close vs close convention
- ✅ Creazione execution_prices view

## # TEST REQUIREMENTS

Ogni modifica deve includere:
1. **Schema validation test**: verifica struttura tabelle
2. **Coherence test**: verifica cross-table consistency  
3. **Business rules test**: verifica vincoli di business
4. **Integration test**: verifica flussi end-to-end

## # APPROVAL PROCESS

1. **Developer**: modifica codice + test
2. **Schema validation**: esegue test suite
3. **Code review**: verifica coerenza DIPF/DDCT
4. **Documentation update**: aggiorna questo documento
5. **Version bump**: aggiorna numero versione

---
**Questo documento è vincolante. Modifiche solo con processo formale.**
