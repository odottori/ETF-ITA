#!/usr/bin/env python3
"""
Extend Historical Data - ETF Italia Project v10
Estende storico dati al 2010+ per certificazione completa
"""

import sys
import os
import json
import yfinance as yf
import pandas as pd
import duckdb
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def extend_historical_data():
    """Estende storico dati al 2010+"""
    
    print("📚 EXTEND HISTORICAL DATA - 2010+ Certification")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    symbols = []
    symbols.extend([etf['symbol'] for etf in config['universe']['core']])
    symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
    symbols.extend([etf['symbol'] for etf in config['universe']['benchmark']])
    
    conn = duckdb.connect(db_path)
    
    try:
        total_extended = 0
        
        for symbol in symbols:
            print(f"\n📈 Estensione storico {symbol}")
            print("-" * 40)
            
            # Verifica data più vecchia nel DB
            oldest_query = "SELECT MIN(date) FROM market_data WHERE symbol = ?"
            oldest_date = conn.execute(oldest_query, [symbol]).fetchone()[0]
            
            if oldest_date:
                target_start = datetime(2010, 1, 1).date()
                
                if oldest_date > target_start:
                    print(f"📅 Estensione richiesta: {target_start} → {oldest_date - timedelta(days=1)}")
                    
                    # Download storico da Yahoo Finance
                    ticker = yf.Ticker(symbol)
                    
                    print(f"   Download storico YF 2010-01-01 → {oldest_date - timedelta(days=1)}")
                    hist = ticker.history(start=target_start, end=oldest_date)
                    
                    if not hist.empty:
                        print(f"   📊 Storico scaricato: {len(hist)} record")
                        
                        # Quality check base
                        hist = hist.dropna()
                        
                        # Validazione quality gates
                        print(f"   🔍 Validazione quality gates...")
                        
                        # Zero check
                        zero_mask = (hist['Close'] <= 0) | (hist['Volume'] < 0)
                        hist = hist[~zero_mask]
                        
                        # Consistency check
                        inconsistent_mask = (hist['High'] < hist['Low']) | (hist['High'] < hist['Close']) | (hist['Low'] > hist['Close'])
                        hist = hist[~inconsistent_mask]
                        
                        # Spike detection (limitato per storico)
                        price_change = hist['Close'].pct_change().abs()
                        spike_mask = price_change > 0.25  # 25% per storico
                        hist = hist[~spike_mask]
                        
                        print(f"   📊 Post-validazione: {len(hist)} record ({len(hist)/3719*100:.1f}% retained)")
                        
                        if hist.empty:
                            print(f"   ❌ Tutti i dati respinti dai quality gates")
                            continue
                        
                        # Prepara dati per insert
                        staging_df = hist.reset_index()
                        staging_df['symbol'] = symbol
                        staging_df['source'] = 'YF_HISTORICAL'
                        
                        # Rinomina colonne
                        staging_df = staging_df.rename(columns={
                            'Date': 'date',
                            'Open': 'open',
                            'High': 'high', 
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        })
                        
                        # Gestisci adj_close
                        if 'Adj Close' in staging_df.columns:
                            staging_df = staging_df.rename(columns={'Adj Close': 'adj_close'})
                        else:
                            staging_df['adj_close'] = staging_df['close']
                        
                        # Insert in staging e merge
                        conn.execute("DELETE FROM staging_data WHERE symbol = ?", [symbol])
                        
                        for _, row in staging_df.iterrows():
                            conn.execute("""
                            INSERT INTO staging_data 
                            (symbol, date, high, low, close, adj_close, volume, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, [
                                row['symbol'], row['date'], row['high'], 
                                row['low'], row['close'], row['adj_close'], row['volume'], row['source']
                            ])
                        
                        # Merge in market_data
                        conn.execute("""
                        INSERT OR REPLACE INTO market_data 
                        (symbol, date, high, low, close, adj_close, volume, source)
                        SELECT symbol, date, high, low, close, adj_close, volume, source
                        FROM staging_data
                        WHERE symbol = ?
                        """, [symbol])
                        
                        print(f"   ✅ {symbol}: {len(staging_df)} record storici inseriti")
                        total_extended += len(staging_df)
                        
                        # Verifica nuova copertura
                        new_oldest = conn.execute(oldest_query, [symbol]).fetchone()[0]
                        print(f"   📅 Nuovo periodo: {new_oldest} → {datetime.now().date()}")
                        
                        # Calcola anni coperti
                        years_covered = (datetime.now().year - new_oldest.year) + 1
                        print(f"   📊 Anni coperti: {years_covered}")
                        
                    else:
                        print(f"   ❌ Nessun dato storico disponibile per {symbol}")
                else:
                    print(f"   ✅ Storico già completo dal {oldest_date}")
            else:
                print(f"   ⚠️ Nessun dato esistente per {symbol}")
        
        conn.commit()
        
        print(f"\n🎉 ESTENSIONE STORICO COMPLETATA")
        print(f"📊 Totali record aggiunti: {total_extended}")
        
        # Ri-esegui audit per verificare certificazione
        print(f"\n🔍 VERIFICA POST-ESTENSIONE:")
        print("-" * 40)
        
        for symbol in symbols:
            oldest = conn.execute("SELECT MIN(date) FROM market_data WHERE symbol = ?", [symbol]).fetchone()[0]
            count = conn.execute("SELECT COUNT(*) FROM market_data WHERE symbol = ?", [symbol]).fetchone()[0]
            
            if oldest:
                years = (datetime.now().year - oldest.year) + 1
                expected_days = years * 252
                coverage = (count / expected_days) * 100
                
                status = "✅ CERTIFICATO" if coverage >= 80 else "⚠️ PARZIALE" if coverage >= 60 else "❌ INSUFFICIENTE"
                print(f"{symbol}: {status} ({coverage:.1f}% coverage, {count} records, {oldest})")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore estensione: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = extend_historical_data()
    sys.exit(0 if success else 1)
