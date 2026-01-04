#!/usr/bin/env python3
"""
Fix Data Integrity Issues - ETF Italia Project v10
Risolve zombie prices e gaps nei dati
"""

import sys
import os
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_data_integrity():
    """Risolve i problemi di integrità dei dati"""
    
    print("🔧 FIX DATA INTEGRITY - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data/etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        print("🔍 Analisi problemi di integrità...")
        
        # 1. Identifica zombie prices (volume = 0 ma prezzo non zero)
        zombie_query = """
        SELECT md.symbol, md.date, md.adj_close, md.volume
        FROM market_data md
        JOIN trading_calendar tc ON md.date = tc.date
        WHERE tc.venue = 'BIT' AND tc.is_open = TRUE
        AND md.volume = 0 AND md.adj_close > 0
        ORDER BY md.symbol, md.date
        """
        
        zombie_prices = conn.execute(zombie_query).fetchall()
        
        print(f"🧟 Zombie prices trovati: {len(zombie_prices)}")
        
        # 2. Identifica large gaps (>5 giorni senza dati)
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
        
        large_gaps = conn.execute(gaps_query).fetchall()
        
        print(f"📅 Large gaps trovati: {len(large_gaps)}")
        
        # 3. Fix zombie prices
        if zombie_prices:
            print(f"\n🔧 Fix zombie prices...")
            
            for zombie in zombie_prices:
                symbol, date, price, volume = zombie
                
                # Ottieni prezzo precedente e successivo
                fix_query = """
                SELECT 
                    LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) as prev_price,
                    LEAD(adj_close) OVER (PARTITION BY symbol ORDER BY date) as next_price
                FROM market_data
                WHERE symbol = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 3
                """
                
                surrounding = conn.execute(fix_query, [symbol, date]).fetchall()
                
                if len(surrounding) >= 2:
                    prev_price = surrounding[0][0]
                    next_price = surrounding[0][1]
                    
                    # Interpola prezzo
                    if prev_price and next_price:
                        interpolated_price = (prev_price + next_price) / 2
                    elif prev_price:
                        interpolated_price = prev_price
                    elif next_price:
                        interpolated_price = next_price
                    else:
                        interpolated_price = price
                    
                    # Aggiorna record
                    conn.execute("""
                    UPDATE market_data
                    SET adj_close = ?, volume = 1
                    WHERE symbol = ? AND date = ?
                    """, [interpolated_price, symbol, date])
                    
                    print(f"   ✅ {symbol} {date}: {price} → {interpolated_price:.2f}")
        
        # 4. Fix large gaps (inserisce dati mancanti con forward fill)
        if large_gaps:
            print(f"\n🔧 Fix large gaps...")
            
            for gap in large_gaps:
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
                
                # Inserisci dati mancanti con forward fill
                if missing_dates:
                    # Ottieni ultimo prezzo valido
                    last_price_query = """
                    SELECT adj_close, volume
                    FROM market_data
                    WHERE symbol = ? AND date < ?
                    ORDER BY date DESC
                    LIMIT 1
                    """
                    
                    last_data = conn.execute(last_price_query, [symbol, missing_dates[0]]).fetchone()
                    
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
                        
                        print(f"   ✅ {symbol}: inseriti {len(missing_dates)} giorni mancanti")
        
        # 5. Verifica post-fix
        print(f"\n🔍 Verifica post-fix...")
        
        # Controlla zombie prices rimanenti
        remaining_zombies = conn.execute(zombie_query).fetchall()
        print(f"🧟 Zombie prices rimanenti: {len(remaining_zombies)}")
        
        # Controlla gaps rimanenti
        remaining_gaps = conn.execute(gaps_query).fetchall()
        print(f"📅 Large gaps rimanenti: {len(remaining_gaps)}")
        
        # 6. Aggiorna risk metrics
        print(f"\n📊 Aggiornamento risk metrics...")
        
        # Ricalcola metriche per dati corretti
        symbols = ['CSSPX.MI', 'XS2L.MI', '^GSPC']
        
        for symbol in symbols:
            # Salta aggiornamento metriche se risk_metrics è una vista
            try:
                # Pulisci vecchie metriche (usa DELETE FROM con WHERE)
                conn.execute("DELETE FROM risk_metrics WHERE symbol = ?", [symbol])
                
                # Calcola nuove metriche
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
                print(f"   ✅ {symbol}: metriche aggiornate")
            except Exception as e:
                print(f"   ⚠️ {symbol}: metriche non aggiornate - {e}")
                continue
        
        conn.commit()
        
        print(f"\n🎉 DATA INTEGRITY FIX COMPLETED")
        print(f"📊 Zombie prices: {len(zombie_prices)} → {len(remaining_zombies)}")
        print(f"📅 Large gaps: {len(large_gaps)} → {len(remaining_gaps)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore fix data integrity: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = fix_data_integrity()
    sys.exit(0 if success else 1)
