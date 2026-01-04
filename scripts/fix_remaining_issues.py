#!/usr/bin/env python3
"""
Fix Remaining Issues with Free Data Sources - ETF Italia Project v10
Risolve large gaps rimanenti usando fonti dati gratuite
"""

import sys
import os
import duckdb
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_remaining_issues():
    """Risolve i problemi rimanenti usando fonti free"""
    
    print("🔧 FIX REMAINING ISSUES - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        print("🔍 Analisi problemi rimanenti...")
        
        # 1. Analizza large gaps rimanenti
        gaps_query = """
        WITH gaps AS (
            SELECT 
                symbol,
                date,
                LAG(date) OVER (PARTITION BY symbol ORDER BY date) as prev_date
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI', '^GSPC')
        )
        SELECT symbol, date, prev_date, 
               (date - prev_date) as gap_days
        FROM gaps
        WHERE prev_date IS NOT NULL
        AND (date - prev_date) > 5
        ORDER BY symbol, date
        """
        
        remaining_gaps = conn.execute(gaps_query).fetchall()
        
        print(f"📅 Large gaps rimanenti: {len(remaining_gaps)}")
        
        # 2. Fix large gaps con Yahoo Finance
        if remaining_gaps:
            print(f"\n🔧 Fix large gaps con Yahoo Finance...")
            
            for gap in remaining_gaps:
                symbol, date, prev_date, gap_days = gap
                
                # Genera date mancanti
                missing_dates = []
                current_date = prev_date + timedelta(days=1)
                
                while current_date < date:
                    # Verifica se è giorno di trading
                    trading_check = conn.execute("""
                    SELECT is_open FROM trading_calendar 
                    WHERE date = ? AND venue = 'BIT'
                    """, [current_date]).fetchone()
                    
                    if trading_check and trading_check[0]:
                        missing_dates.append(current_date)
                    
                    current_date += timedelta(days=1)
                
                if missing_dates:
                    print(f"   📊 {symbol}: {len(missing_dates)} giorni mancanti ({missing_dates[0]} → {missing_dates[-1]})")
                    
                    # Scarica dati da Yahoo Finance
                    try:
                        ticker = yf.Ticker(symbol)
                        start_date = missing_dates[0]
                        end_date = missing_dates[-1] + timedelta(days=1)
                        
                        data = ticker.history(start=start_date, end=end_date)
                        
                        if not data.empty:
                            # Inserisci dati mancanti
                            for missing_date in missing_dates:
                                if missing_date in data.index:
                                    row = data.loc[missing_date]
                                    
                                    conn.execute("""
                                    INSERT OR REPLACE INTO market_data 
                                    (symbol, date, high, low, close, adj_close, volume)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, [
                                        symbol, missing_date,
                                        row['High'], row['Low'], row['Close'], 
                                        row['Adj Close'], row['Volume']
                                    ])
                            
                            print(f"   ✅ {symbol}: {len(data)} giorni recuperati da Yahoo Finance")
                        else:
                            print(f"   ⚠️ {symbol}: nessun dato da Yahoo Finance")
                            
                    except Exception as e:
                        print(f"   ❌ {symbol}: errore Yahoo Finance - {e}")
                        # Fallback: usa forward fill
                        last_data = conn.execute("""
                        SELECT adj_close, volume
                        FROM market_data
                        WHERE symbol = ? AND date < ?
                        ORDER BY date DESC
                        LIMIT 1
                        """, [symbol, missing_dates[0]]).fetchone()
                        
                        if last_data:
                            last_price, last_volume = last_data
                            
                            for missing_date in missing_dates:
                                conn.execute("""
                                INSERT INTO market_data (symbol, date, high, low, close, adj_close, volume)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, [
                                    symbol, missing_date,
                                    last_price, last_price, last_price,
                                    last_price, last_volume
                                ])
                            
                            print(f"   🔄 {symbol}: {len(missing_dates)} giorni con forward fill")
        
        # 3. Fix risk metrics (ricrea tabella se è vista)
        print(f"\n📊 Fix risk metrics...")
        
        try:
            # Controlla se risk_metrics è vista o tabella
            table_info = conn.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = 'risk_metrics' AND table_type = 'BASE TABLE'
            """).fetchall()
            
            if not table_info:
                print("   📊 Creazione tabella risk_metrics...")
                
                # Crea tabella risk_metrics
                conn.execute("""
                CREATE TABLE risk_metrics (
                    symbol VARCHAR NOT NULL,
                    date DATE NOT NULL,
                    adj_close DOUBLE,
                    daily_return DOUBLE,
                    sma_20 DOUBLE,
                    sma_50 DOUBLE,
                    sma_200 DOUBLE,
                    volatility_20d DOUBLE,
                    drawdown_pct DOUBLE,
                    PRIMARY KEY (symbol, date)
                )
                """)
                
                # Calcola metriche
                symbols = ['CSSPX.MI', 'XS2L.MI', '^GSPC']
                
                for symbol in symbols:
                    print(f"   📈 Calcolo metriche {symbol}...")
                    
                    metrics_query = """
                    INSERT INTO risk_metrics (
                        symbol, date, adj_close, daily_return, 
                        sma_20, sma_50, sma_200, volatility_20d, drawdown_pct
                    )
                    SELECT 
                        symbol,
                        date,
                        adj_close,
                        adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1,
                        AVG(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
                        AVG(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW),
                        AVG(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW),
                        STDDEV(adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1) 
                            OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) * SQRT(252),
                        (adj_close / MAX(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS UNBOUNDED PRECEDING)) - 1
                    FROM market_data
                    WHERE symbol = ? AND adj_close IS NOT NULL
                    ORDER BY date
                    """
                    
                    conn.execute(metrics_query, [symbol])
                
                print("   ✅ Risk metrics calcolate")
            else:
                print("   ✅ Risk metrics già esistente")
                
        except Exception as e:
            print(f"   ⚠️ Risk metrics: {e}")
        
        # 4. Verifica finale
        print(f"\n🔍 Verifica finale...")
        
        # Controlla gaps rimanenti
        final_gaps = conn.execute(gaps_query).fetchall()
        print(f"📅 Large gaps finali: {len(final_gaps)}")
        
        # Controlla dati totali
        total_data = conn.execute("""
        SELECT COUNT(*) as total_records, COUNT(DISTINCT symbol) as symbols, 
               COUNT(DISTINCT date) as dates
        FROM market_data
        """).fetchone()
        
        print(f"📊 Dati finali: {total_data[0]} records, {total_data[1]} simboli, {total_data[2]} date")
        
        # Controlla risk metrics
        risk_metrics_count = conn.execute("""
        SELECT COUNT(*) FROM risk_metrics
        """).fetchone()[0]
        
        print(f"📈 Risk metrics: {risk_metrics_count} records")
        
        conn.commit()
        
        print(f"\n🎉 REMAINING ISSUES FIX COMPLETED")
        print(f"📅 Large gaps: {len(remaining_gaps)} → {len(final_gaps)}")
        print(f"📊 Dati aggiunti: {total_data[0]} records totali")
        print(f"📈 Risk metrics: {risk_metrics_count} records")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore fix remaining issues: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = fix_remaining_issues()
    sys.exit(0 if success else 1)
