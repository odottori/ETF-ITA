#!/usr/bin/env python3
"""
Ingest Data - ETF Italia Project v10
Download e validazione dati di mercato da Yahoo Finance con quality gates
"""

import sys
import os
import json
import yfinance as yf
import pandas as pd
import duckdb
import requests
from datetime import datetime, timedelta
import hashlib

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_config():
    """Carica configurazione"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def download_stooq_data(symbol, start_date, end_date):
    """Download dati da Stooq.com come fallback"""
    try:
        # Converti simbolo per Stooq (es. XS2L.MI -> xs2l.mi)
        stooq_symbol = symbol.lower().replace('.', '')
        
        # Stooq API - formato CSV con data range
        url = f"https://stooq.com/q/l/?s={stooq_symbol}&i=d"
        
        print(f"   🔄 Tentativo download Stooq per {symbol}...")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200 and response.text.strip():
            # Parse CSV data
            lines = response.text.strip().split('\n')
            if len(lines) > 1:  # Header + data
                data = []
                for line in lines[1:]:  # Skip header
                    parts = line.split(',')
                    if len(parts) >= 6:
                        try:
                            date_str = parts[0]
                            open_price = float(parts[1])
                            high_price = float(parts[2])
                            low_price = float(parts[3])
                            close_price = float(parts[4])
                            volume = int(parts[5]) if parts[5] else 0
                            
                            # Filtra per range date
                            record_date = pd.to_datetime(date_str).date()
                            if start_date <= record_date <= end_date:
                                data.append({
                                    'Date': pd.to_datetime(date_str),
                                    'Open': open_price,
                                    'High': high_price,
                                    'Low': low_price,
                                    'Close': close_price,
                                    'Volume': volume
                                })
                        except (ValueError, IndexError):
                            continue
                
                if data:
                    df = pd.DataFrame(data)
                    df.set_index('Date', inplace=True)
                    df.sort_index(inplace=True)
                    print(f"   ✅ Stooq: {len(df)} record scaricati (range filtrato)")
                    return df
        
        print(f"   ❌ Stooq: nessun dato disponibile")
        return None
        
    except Exception as e:
        print(f"   ❌ Errore Stooq: {e}")
        return None

def validate_data_quality(df, symbol):
    """Validazione quality gates su dati"""
    
    validation_results = {
        'total_records': len(df),
        'accepted_records': 0,
        'rejected_records': 0,
        'rejection_reasons': []
    }
    
    if df.empty:
        return validation_results
    
    # Quality Gate 1: Zero Check
    zero_price_mask = (df['Close'] <= 0) | (df['Volume'] < 0)
    zero_count = zero_price_mask.sum()
    if zero_count > 0:
        validation_results['rejection_reasons'].append(f"Zero/negative prices: {zero_count}")
    
    # Quality Gate 2: Consistency Check
    inconsistent_mask = (df['High'] < df['Low']) | (df['High'] < df['Close']) | (df['Low'] > df['Close'])
    inconsistent_count = inconsistent_mask.sum()
    if inconsistent_count > 0:
        validation_results['rejection_reasons'].append(f"Inconsistent OHLC: {inconsistent_count}")
    
    # Quality Gate 3: Spike Detection (>15%)
    df_sorted = df.sort_index()
    price_change = df_sorted['Close'].pct_change().abs()
    spike_mask = price_change > 0.15
    spike_count = spike_mask.sum()
    if spike_count > 0:
        validation_results['rejection_reasons'].append(f"Price spikes >15%: {spike_count}")
    
    # Quality Gate 4: Zombie Price Detection
    zombie_mask = (df['Volume'] == 0) & (df['Close'].duplicated(keep=False))
    zombie_count = zombie_mask.sum()
    if zombie_count > 0:
        validation_results['rejection_reasons'].append(f"Zombie prices (vol=0, price repeated): {zombie_count}")
    
    # Applica filtri
    valid_mask = ~(zero_price_mask | inconsistent_mask | spike_mask)
    valid_df = df[valid_mask].copy()
    
    validation_results['accepted_records'] = len(valid_df)
    validation_results['rejected_records'] = validation_results['total_records'] - validation_results['accepted_records']
    
    return validation_results, valid_df

def ingest_data():
    """Ingestione completa dati di mercato"""
    
    config = get_config()
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Genera run_id
    run_id = f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    conn = duckdb.connect(db_path)
    
    try:
        print(f"🔄 Ingestion dati - Run ID: {run_id}")
        
        # Raccolta simboli da universe
        symbols = []
        symbols.extend([etf['symbol'] for etf in config['universe']['core']])
        symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
        symbols.extend([etf['symbol'] for etf in config['universe']['benchmark']])
        
        print(f"📊 Simboli da processare: {symbols}")
        
        total_accepted = 0
        total_rejected = 0
        all_rejection_reasons = []
        
        for symbol in symbols:
            print(f"\n📈 Processando {symbol}...")
            
            try:
                # Download dati yfinance
                ticker = yf.Ticker(symbol)
                
                # Ultima data nel database per questo simbolo
                last_date_query = "SELECT MAX(date) FROM market_data WHERE symbol = ?"
                last_date = conn.execute(last_date_query, [symbol]).fetchone()[0]
                
                # Calcola range date
                end_date = datetime.now().date()
                if last_date:
                    start_date = last_date + timedelta(days=1)
                else:
                    start_date = end_date - timedelta(days=365)  # 1 anno di dati iniziali
                
                # Download primario Yahoo Finance
                print(f"   Download YF {start_date} → {end_date}")
                hist = ticker.history(start=start_date, end=end_date)
                
                # Se YF fallisce o dati insufficienti, prova Stooq
                if hist.empty or len(hist) < 10:
                    print(f"   ⚠️ YF dati insufficienti ({len(hist)} record)")
                    stooq_data = download_stooq_data(symbol, start_date, end_date)
                    if stooq_data is not None and not stooq_data.empty:
                        hist = stooq_data
                        print(f"   ✅ Usati dati Stooq: {len(hist)} record")
                    else:
                        print(f"   ❌ Nessun dato disponibile da nessuna fonte")
                        continue
                
                # Validazione quality gates
                validation_results, valid_df = validate_data_quality(hist, symbol)
                
                print(f"   📊 Records: {validation_results['total_records']} totali, "
                      f"{validation_results['accepted_records']} accettati, "
                      f"{validation_results['rejected_records']} respinti")
                
                if validation_results['rejection_reasons']:
                    print(f"   ⚠️ Rejection reasons: {', '.join(validation_results['rejection_reasons'])}")
                    all_rejection_reasons.extend(validation_results['rejection_reasons'])
                
                # Se troppi respinti (>15%), prova Stooq per recuperare
                if validation_results['rejected_records'] > 0 and validation_results['rejected_records'] / validation_results['total_records'] > 0.15:
                    print(f"   🔄 Troppe rejections ({validation_results['rejected_records']}/{validation_results['total_records']}), provo Stooq...")
                    stooq_fallback = download_stooq_data(symbol, start_date, end_date)
                    
                    if stooq_fallback is not None and not stooq_fallback.empty:
                        # Validazione dati Stooq
                        stooq_validation, stooq_valid = validate_data_quality(stooq_fallback, symbol)
                        
                        if stooq_validation['accepted_records'] > validation_results['accepted_records']:
                            print(f"   ✅ Stooq migliore: {stooq_validation['accepted_records']} vs {validation_results['accepted_records']}")
                            valid_df = stooq_valid
                            validation_results = stooq_validation
                            all_rejection_reasons.append(f"Used Stooq fallback for {symbol}")
                
                # Insert in staging table
                if not valid_df.empty:
                    # Prepara dati per staging
                    staging_df = valid_df.reset_index()
                    staging_df['symbol'] = symbol
                    staging_df['source'] = 'YF'
                    
                    # Rinomina colonne per DB
                    staging_df = staging_df.rename(columns={
                        'Date': 'date',
                        'Open': 'open',
                        'High': 'high', 
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    
                    # Gestisci adj_close (potrebbe non esistere)
                    if 'Adj Close' in staging_df.columns:
                        staging_df = staging_df.rename(columns={'Adj Close': 'adj_close'})
                    else:
                        staging_df['adj_close'] = staging_df['close']  # fallback
                    
                    # Insert in staging
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
                    
                    # Merge in market_data (solo dati validi)
                    conn.execute("""
                    INSERT OR REPLACE INTO market_data 
                    (symbol, date, high, low, close, adj_close, volume, source)
                    SELECT symbol, date, high, low, close, adj_close, volume, source
                    FROM staging_data
                    WHERE symbol = ?
                    """, [symbol])
                    
                    print(f"   ✅ {symbol}: {len(valid_df)} record inseriti in market_data")
                
                total_accepted += validation_results['accepted_records']
                total_rejected += validation_results['rejected_records']
                
            except Exception as e:
                print(f"   ❌ Errore processamento {symbol}: {e}")
                all_rejection_reasons.append(f"{symbol}: {str(e)}")
                continue
        
        # Audit record
        rejection_summary = "; ".join(all_rejection_reasons) if all_rejection_reasons else "No rejections"
        
        # Ottieni prossimo ID
        next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM ingestion_audit").fetchone()[0]
        
        conn.execute("""
        INSERT INTO ingestion_audit 
        (id, run_id, provider, start_date, end_date, records_accepted, records_rejected, rejection_reasons, provider_schema_hash)
        VALUES (?, ?, 'YF', ?, ?, ?, ?, ?, ?)
        """, [
            next_id,
            run_id,
            datetime.now().date() - timedelta(days=1),  # semplificato
            datetime.now().date(),
            total_accepted,
            total_rejected,
            rejection_summary,
            hashlib.md5(f"yfinance_{datetime.now().date()}".encode()).hexdigest()
        ])
        
        conn.commit()
        
        print(f"\n🎉 Ingestion completata!")
        print(f"📊 Totali: {total_accepted} record accettati, {total_rejected} record respinti")
        print(f"🔍 Run ID: {run_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore ingestion: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    success = ingest_data()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
