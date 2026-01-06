#!/usr/bin/env python3
"""
Setup Database - ETF Italia Project v10
Crea database DuckDB con tabelle, viste e indici secondo DATADICTIONARY
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root al path per import futuri
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_database():
    """Setup completo del database"""
    
    # Path database
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Connessione DB
    conn = duckdb.connect(db_path)
    
    try:
        print(f"Setup database: {db_path}")
        
        # 1. Creazione tabelle principali
        print("Creazione tabelle...")
        
        # Tabella market_data (master data)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
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
        """)
        
        # Tabella staging_data (transito)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS staging_data (
            symbol VARCHAR NOT NULL,
            date DATE NOT NULL,
            adj_close DOUBLE CHECK (adj_close > 0),
            close DOUBLE CHECK (close > 0),
            high DOUBLE CHECK (high >= 0),
            low DOUBLE CHECK (low >= 0),
            volume BIGINT CHECK (volume >= 0),
            source VARCHAR DEFAULT 'YF',
            PRIMARY KEY (symbol, date)
        )
        """)
        
        # Tabella fiscal_ledger (registro operazioni)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_ledger (
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
        """)
        
        # Tabella ingestion_audit
        conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_audit (
            id INTEGER PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL DEFAULT 'YF',
            symbol VARCHAR,
            start_date DATE,
            end_date DATE,
            records_accepted INTEGER DEFAULT 0,
            records_rejected INTEGER DEFAULT 0,
            rejection_reasons TEXT,
            provider_schema_hash VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tabella trading_calendar
        conn.execute("""
        CREATE TABLE IF NOT EXISTS trading_calendar (
            venue VARCHAR NOT NULL,
            date DATE NOT NULL,
            is_open BOOLEAN NOT NULL DEFAULT TRUE,
            PRIMARY KEY (venue, date)
        )
        """)
        
        # Tabella symbol_registry
        conn.execute("""
        CREATE TABLE IF NOT EXISTS symbol_registry (
            symbol VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            status VARCHAR DEFAULT 'ACTIVE',
            category VARCHAR NOT NULL,
            currency VARCHAR NOT NULL,
            distribution_policy VARCHAR DEFAULT 'ACC',
            tax_category VARCHAR DEFAULT 'OICR_ETF',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tabella orders (gestione ordini)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
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
        """)
        
        # Tabella trade_journal (per tracking override)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_journal (
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
        """)
        
        # Tabella tax_loss_carryforward (zainetto fiscale)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_loss_carryforward (
            id INTEGER PRIMARY KEY,
            symbol VARCHAR NOT NULL,
            realize_date DATE NOT NULL,
            loss_amount DOUBLE NOT NULL CHECK (loss_amount < 0),
            used_amount DOUBLE DEFAULT 0.0 CHECK (used_amount >= 0),
            expires_at DATE NOT NULL,
            tax_category VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (used_amount <= ABS(loss_amount))
        )
        """)
        
        print("Tabelle create")
        
        # 2. Creazione indici
        print("Creazione indici...")
        
        indici = [
            "CREATE INDEX IF NOT EXISTS idx_market_data_symbol_date ON market_data(symbol, date)",
            "CREATE INDEX IF NOT EXISTS idx_market_data_date ON market_data(date)",
            "CREATE INDEX IF NOT EXISTS idx_fiscal_ledger_date ON fiscal_ledger(date)",
            "CREATE INDEX IF NOT EXISTS idx_fiscal_ledger_symbol ON fiscal_ledger(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_fiscal_ledger_type ON fiscal_ledger(type)",
            "CREATE INDEX IF NOT EXISTS idx_ingestion_audit_run_id ON ingestion_audit(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_trading_calendar_venue_date ON trading_calendar(venue, date)",
            "CREATE INDEX IF NOT EXISTS idx_trade_journal_run_id ON trade_journal(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_tax_loss_expires ON tax_loss_carryforward(expires_at)"
        ]
        
        for idx in indici:
            conn.execute(idx)
        
        print(" Indici creati")
        
        # 3. Creazione viste (analytics)
        print(" Creazione viste analytics...")
        
        # Vista risk_metrics
        conn.execute("""
        CREATE OR REPLACE VIEW risk_metrics AS
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
        """)
        
        # Vista portfolio_summary
        conn.execute("""
        CREATE OR REPLACE VIEW portfolio_summary AS
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
        """)
        
        # Vista execution_prices per trading realistico
        conn.execute("""
        CREATE OR REPLACE VIEW execution_prices AS
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
        """)
        
        print(" Viste create")
        
        # 4. Insert deposito iniziale (CRITICO)
        print(" Insert deposito iniziale...")
        
        start_capital = config['settings']['start_capital']
        today = datetime.now().date()
        
        # Ottieni prossimo ID disponibile
        next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
        
        conn.execute("""
        INSERT OR IGNORE INTO fiscal_ledger 
        (id, date, type, symbol, qty, price, fees, tax_paid, pmc_snapshot, run_id)
        VALUES (?, ?, 'DEPOSIT', 'CASH', ?, 1.0, 0.0, 0.0, 1.0, ?)
        """, [next_id, today, start_capital, f"setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"])
        
        print(f" Deposito iniziale di €{start_capital:,.2f} inserito")
        
        # 5. Setup trading calendar base (BIT)
        print(" Setup trading calendar base...")
        
        # Inserisci giorni feriali Italiani come aperti (semplificato)
        start_date = '2020-01-01'
        end_date = '2025-12-31'
        
        conn.execute(f"""
        INSERT OR IGNORE INTO trading_calendar (venue, date, is_open)
        SELECT 'BIT', 
               generate_series::date, 
               EXTRACT(ISODOW FROM generate_series::date) NOT IN (6, 7) as is_open
        FROM generate_series('{start_date}'::DATE, '{end_date}'::DATE, INTERVAL '1 day')
        """)
        
        print(" Trading calendar base creato")
        
        # Commit finale
        conn.commit()
        print(" Database setup completato con successo!")
        
        # Verifica
        result = conn.execute("SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'main'").fetchone()
        print(f" Database contiene {result[0]} tabelle")
        
        return True
        
    except Exception as e:
        print(f" Errore durante setup database: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
