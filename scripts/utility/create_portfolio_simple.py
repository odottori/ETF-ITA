#!/usr/bin/env python3
"""
Create Portfolio Overview - ETF Italia Project v10
Crea vista portfolio_overview per backtest e stress test
"""

import sys
import os
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_portfolio_overview():
    """Crea vista portfolio_overview per backtest e stress test"""
    
    print("📊 CREATE PORTFOLIO OVERVIEW - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        print("📊 Creazione vista portfolio_overview...")
        
        # Crea vista portfolio_overview semplificata
        conn.execute("""
        CREATE OR REPLACE VIEW portfolio_overview AS
        SELECT 
            date,
            symbol,
            adj_close,
            volume,
            0 as market_value,
            0 as qty,
            0 as cash
        FROM market_data
        WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        ORDER BY date, symbol
        """)
        
        print("✅ Vista portfolio_overview creata")
        
        # Crea vista portfolio_summary per aggregati giornalieri
        conn.execute("""
        CREATE OR REPLACE VIEW portfolio_summary AS
        SELECT 
            date,
            AVG(adj_close) as avg_adj_close,
            SUM(volume) as total_volume,
            COUNT(DISTINCT symbol) as symbols_count
        FROM portfolio_overview
        GROUP BY date
        ORDER BY date
        """)
        
        print("✅ Vista portfolio_summary creata")
        
        conn.commit()
        
        print(f"\n🎉 PORTFOLIO OVERVIEW CREATION COMPLETED")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore creazione portfolio overview: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = create_portfolio_overview()
    sys.exit(0 if success else 1)
