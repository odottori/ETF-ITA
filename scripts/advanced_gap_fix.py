#!/usr/bin/env python3
"""
Advanced Gap Fix with Multiple Sources - ETF Italia Project v10
Usa multiple fonti dati per riempire gaps
"""

import sys
import os
import duckdb
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def advanced_gap_fix():
    """Fix avanzato gaps usando multiple fonti"""
    
    print("🔧 ADVANCED GAP FIX - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        print("🔍 Analisi gaps specifici...")
        
        # 1. Analizza gaps specifici per simbolo
        gaps_query = """
        WITH gaps AS (
            SELECT 
                symbol,
                date,
                LAG(date) OVER (PARTITION BY symbol ORDER BY date) as prev_date,
                (date - LAG(date) OVER (PARTITION BY symbol ORDER BY date)) as gap_days
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        )
        SELECT symbol, date, prev_date, gap_days
        FROM gaps
        WHERE prev_date IS NOT NULL
        AND gap_days > 5
        ORDER BY symbol, gap_days DESC
        """
        
        gaps = conn.execute(gaps_query).fetchall()
        
        print(f"📅 Gaps da analizzare: {len(gaps)}")
        
        # 2. Fix gaps per simbolo
        for symbol in ['CSSPX.MI', 'XS2L.MI']:
            symbol_gaps = [gap for gap in gaps if gap[0] == symbol]
            
            if symbol_gaps:
                print(f"\n🔧 Fix gaps per {symbol}...")
                
                for gap in symbol_gaps[:5]:  # Limita ai primi 5 gaps per simbolo
                    symbol_name, date, prev_date, gap_days = gap
                    
                    print(f"   📅 Gap: {prev_date} → {date} ({gap_days} giorni)")
                    
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
                        print(f"   📊 {len(missing_dates)} giorni mancanti")
                        
                        # Prova Yahoo Finance
                        try:
                            ticker = yf.Ticker(symbol)
                            start_date = missing_dates[0]
                            end_date = missing_dates[-1] + timedelta(days=1)
                            
                            data = ticker.history(start=start_date, end=end_date)
                            
                            if not data.empty:
                                # Inserisci dati
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
                                
                                print(f"   ✅ {len(data)} giorni da Yahoo Finance")
                            else:
                                print(f"   ⚠️ Nessun dato da Yahoo Finance")
                                
                        except Exception as e:
                            print(f"   ❌ Errore Yahoo Finance: {e}")
                        
                        # Prova Stooq come fallback
                        try:
                            stooq_data = get_stooq_data(symbol, missing_dates[0], missing_dates[-1])
                            
                            if stooq_data:
                                for missing_date, price, volume in stooq_data:
                                    conn.execute("""
                                    INSERT OR REPLACE INTO market_data 
                                    (symbol, date, high, low, close, adj_close, volume)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, [
                                        symbol, missing_date,
                                        price, price, price,
                                        price, volume
                                    ])
                                
                                print(f"   ✅ {len(stooq_data)} giorni da Stooq")
                            else:
                                print(f"   ⚠️ Nessun dato da Stooq")
                                
                        except Exception as e:
                            print(f"   ❌ Errore Stooq: {e}")
        
        # 3. Verifica finale
        print(f"\n🔍 Verifica finale...")
        
        final_gaps = conn.execute(gaps_query).fetchall()
        print(f"📅 Gaps finali: {len(final_gaps)}")
        
        # Statistiche finali
        stats = conn.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as symbols,
            COUNT(DISTINCT date) as dates,
            MIN(date) as min_date,
            MAX(date) as max_date
        FROM market_data
        """).fetchone()
        
        print(f"📊 Statistiche finali:")
        print(f"   Records: {stats[0]}")
        print(f"   Simboli: {stats[1]}")
        print(f"   Date: {stats[2]}")
        print(f"   Periodo: {stats[3]} → {stats[4]}")
        
        conn.commit()
        
        print(f"\n🎉 ADVANCED GAP FIX COMPLETED")
        print(f"📅 Gaps processati: {len(gaps)} → {len(final_gaps)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore advanced gap fix: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

def get_stooq_data(symbol, start_date, end_date):
    """Ottieni dati da Stooq"""
    try:
        # Converti simbolo per Stooq
        stooq_symbol = convert_to_stooq(symbol)
        
        # Formatta date
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # URL Stooq
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&d1={start_str}&d2={end_str}&i=d"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            # Parse CSV data
            data = []
            lines = response.text.strip().split('\n')
            
            for line in lines[1:]:  # Skip header
                parts = line.split(',')
                if len(parts) >= 5:
                    date_str = parts[0]
                    open_price = float(parts[1])
                    high_price = float(parts[2])
                    low_price = float(parts[3])
                    close_price = float(parts[4])
                    volume = int(parts[5]) if len(parts) > 5 else 0
                    
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    data.append((date_obj, close_price, volume))
            
            return data
        
    except Exception as e:
        print(f"   Stooq error: {e}")
        return []
    
    return []

def convert_to_stooq(symbol):
    """Converte simbolo per Stooq"""
    mapping = {
        'CSSPX.MI': 'csspx',
        'XS2L.MI': 'xs2l',
        '^GSPC': 'spx'
    }
    return mapping.get(symbol, symbol.lower().replace('.mi', ''))

if __name__ == "__main__":
    success = advanced_gap_fix()
    sys.exit(0 if success else 1)
