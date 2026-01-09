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
import argparse
import time
from typing import Optional, Tuple, Dict, List

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager

def get_config():
    """Carica configurazione"""
    pm = get_path_manager()
    config_path = str(pm.etf_universe_path)
    with open(config_path, 'r') as f:
        return json.load(f)

def download_investing_com_data(symbol: str, start_date, end_date) -> Optional[pd.DataFrame]:
    """Download dati da Investing.com come fallback (via web scraping leggero)"""
    try:
        # Mapping simboli Milano → Investing.com
        investing_map = {
            'CSSPX.MI': 'ishares-core-s-p-500',
            'XS2L.MI': 'xtrackers-s-p-500-2x-leveraged-daily',
            'AGGH.MI': 'ishares-global-aggregate-bond'
        }
        
        if symbol not in investing_map:
            return None
        
        print(f"    Tentativo download Investing.com per {symbol}...")
        # Nota: implementazione placeholder - richiede API key o scraping
        # Per ora ritorna None, da implementare con provider premium
        print(f"    Investing.com: non implementato (richiede API key)")
        return None
        
    except Exception as e:
        print(f"    Errore Investing.com: {e}")
        return None

def download_stooq_data(symbol: str, start_date, end_date) -> Optional[pd.DataFrame]:
    """Download dati da Stooq.com come fallback"""
    try:
        # Converti simbolo per Stooq (es. XS2L.MI → xs2lmi)
        stooq_symbol = symbol.lower().replace('.', '')
        
        # Stooq API - formato CSV con data range
        url = f"https://stooq.com/q/l/?s={stooq_symbol}&i=d"
        
        print(f"    Tentativo download Stooq per {symbol}...")
        time.sleep(0.5)  # Rate limiting
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
                    print(f"    Stooq: {len(df)} record scaricati (range filtrato)")
                    return df
        
        print(f"    Stooq: nessun dato disponibile")
        return None
        
    except Exception as e:
        print(f"    Errore Stooq: {e}")
        return None

def load_manual_csv_data(symbol: str, start_date, end_date) -> Optional[pd.DataFrame]:
    """Carica dati da CSV manuale come ultimo fallback"""
    try:
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'manual', f'{symbol}.csv'
        )
        
        if not os.path.exists(csv_path):
            return None
        
        print(f"    Caricamento CSV manuale per {symbol}...")
        df = pd.read_csv(csv_path, parse_dates=['Date'], index_col='Date')
        
        # Filtra per range date
        df = df[(df.index.date >= start_date) & (df.index.date <= end_date)]
        
        if not df.empty:
            print(f"    CSV manuale: {len(df)} record caricati")
            return df
        
        return None
        
    except Exception as e:
        print(f"    Errore CSV manuale: {e}")
        return None

def validate_data_quality(df, symbol: str) -> Tuple[Dict, pd.DataFrame]:
    """Validazione quality gates su dati"""
    
    validation_results = {
        'total_records': len(df),
        'accepted_records': 0,
        'rejected_records': 0,
        'rejection_reasons': [],
        'coverage_pct': 0.0
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
    price_change = df_sorted['Close'].pct_change(fill_method=None).abs()
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
    
    # Calcola coverage %
    if validation_results['total_records'] > 0:
        validation_results['coverage_pct'] = (validation_results['accepted_records'] / validation_results['total_records']) * 100
    
    return validation_results, valid_df

def download_with_fallback(symbol: str, start_date, end_date) -> Tuple[Optional[pd.DataFrame], str]:
    """Download multi-source con fallback automatico: YF → Stooq → Investing.com → CSV"""
    
    sources = [
        ('YF', lambda: yf.Ticker(symbol).history(start=start_date, end=end_date + timedelta(days=1))),
        ('Stooq', lambda: download_stooq_data(symbol, start_date, end_date)),
        ('Investing.com', lambda: download_investing_com_data(symbol, start_date, end_date)),
        ('CSV Manual', lambda: load_manual_csv_data(symbol, start_date, end_date))
    ]
    
    for source_name, download_func in sources:
        try:
            if source_name == 'YF':
                print(f"   Download {source_name} {start_date} → {end_date}")
            
            data = download_func()
            
            if data is not None and not data.empty and len(data) >= 1:
                if source_name != 'YF':
                    print(f"    {source_name}: {len(data)} record scaricati")
                return data, source_name
            elif source_name == 'YF' and (data is None or data.empty or len(data) < 1):
                print(f"   ️ {source_name} dati insufficienti ({len(data) if data is not None else 0} record)")
        
        except Exception as e:
            print(f"    Errore {source_name}: {e}")
            continue
    
    return None, 'NONE'

def analyze_gaps(conn, symbol: str, start_date, end_date) -> Dict:
    """Analizza gap temporali nei dati per un simbolo"""
    
    result = conn.execute("""
    WITH date_series AS (
        SELECT UNNEST(generate_series(
            ?::DATE,
            ?::DATE,
            INTERVAL '1 day'
        ))::DATE as expected_date
    ),
    actual_dates AS (
        SELECT date FROM market_data WHERE symbol = ?
    )
    SELECT 
        COUNT(DISTINCT ds.expected_date) as expected_days,
        COUNT(DISTINCT ad.date) as actual_days,
        COUNT(DISTINCT ds.expected_date) - COUNT(DISTINCT ad.date) as missing_days
    FROM date_series ds
    LEFT JOIN actual_dates ad ON ds.expected_date = ad.date
    """, [start_date, end_date, symbol]).fetchone()
    
    expected, actual, missing = result
    coverage_pct = (actual / expected * 100) if expected > 0 else 0
    
    return {
        'expected_days': expected,
        'actual_days': actual,
        'missing_days': missing,
        'coverage_pct': coverage_pct
    }

def ingest_data(start_date_override=None, end_date_override=None, full_refresh=False, symbols_filter=None, initial_start_date_override=None):
    """Ingestione completa dati di mercato"""
    
    config = get_config()
    # Initial start date (per nuovi simboli senza storico in DB)
    def _parse_date(s):
        if not s:
            return None
        try:
            return datetime.strptime(str(s), '%Y-%m-%d').date()
        except Exception:
            return None

    initial_start_date_default = _parse_date(config.get('initial_start_date')) or _parse_date(config.get('default_active_from')) or datetime(2010,1,1).date()
    if initial_start_date_override is not None:
        initial_start_date_default = initial_start_date_override


    # Start date default per simboli nuovi (inception): di default 2010-01-01 o quanto definito in config
    initial_start_date_str = (config.get('initial_start_date') or config.get('default_active_from') or '2010-01-01')
    try:
        initial_start_date_cfg = datetime.strptime(initial_start_date_str, '%Y-%m-%d').date()
    except Exception:
        initial_start_date_cfg = datetime(2010, 1, 1).date()
    initial_start_date = initial_start_date_override or initial_start_date_cfg

    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    # Genera run_id
    run_id = f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    conn = duckdb.connect(db_path)
    
    try:
        print(f" Ingestion dati - Run ID: {run_id}")
        
        # Raccolta simboli da universe (supporta tutte le strutture)
        symbols = []
        universe = config['universe']
        
        # Nuova struttura v2 (equity_usa, equity_international, equity_global, bond, alternative)
        if 'equity_usa' in universe:
            symbols.extend([etf['symbol'] for etf in universe.get('equity_usa', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('equity_international', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('equity_global', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('bond', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('alternative', [])])
        # Struttura v1 (equity_core, bond, alternative)
        elif 'equity_core' in universe:
            symbols.extend([etf['symbol'] for etf in universe.get('equity_core', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('bond', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('alternative', [])])
        # Vecchia struttura (core, satellite)
        else:
            symbols.extend([etf['symbol'] for etf in universe.get('core', [])])
            symbols.extend([etf['symbol'] for etf in universe.get('satellite', [])])
        
        # Benchmark sempre presente
        symbols.extend([etf['symbol'] for etf in universe.get('benchmark', [])])
        


        # Filtro simboli (opzionale): consente re-ingest chirurgico su uno o piu ticker
        if symbols_filter:
            filt = {str(s).strip() for s in symbols_filter if s and str(s).strip()}
            symbols = [s for s in symbols if s in filt]
            if not symbols:
                print('WARNING: Nessun simbolo corrisponde al filtro richiesto; nulla da fare.')
                return True

        print(f" Simboli da processare: {symbols}")
        
        total_accepted = 0
        total_rejected = 0
        all_rejection_reasons = []
        
        for symbol in symbols:
            print(f"\n Processando {symbol}...")
            
            try:
                # Download dati yfinance
                ticker = yf.Ticker(symbol)
                
                # Calcola range date
                end_date = end_date_override or datetime.now().date()

                if full_refresh:
                    conn.execute("DELETE FROM market_data WHERE symbol = ?", [symbol])
                    conn.execute("DELETE FROM staging_data WHERE symbol = ?", [symbol])
                    last_date = None
                else:
                    # Ultima data nel database per questo simbolo
                    last_date_query = "SELECT MAX(date) FROM market_data WHERE symbol = ?"
                    last_date = conn.execute(last_date_query, [symbol]).fetchone()[0]

                if start_date_override is not None:
                    start_date = start_date_override
                elif last_date:
                    start_date = last_date + timedelta(days=1)
                else:
                    start_date = initial_start_date  # 1 anno di dati iniziali

                if start_date > end_date:
                    print(f"   ️ Range date vuoto: {start_date} → {end_date} (skip)")
                    continue
                
                # Download multi-source con fallback automatico
                hist, source_used = download_with_fallback(symbol, start_date, end_date)
                
                if hist is None or hist.empty:
                    print(f"    Nessun dato disponibile da nessuna fonte")
                    continue
                
                # Validazione quality gates
                validation_results, valid_df = validate_data_quality(hist, symbol)
                
                print(f"    Records: {validation_results['total_records']} totali, "
                      f"{validation_results['accepted_records']} accettati, "
                      f"{validation_results['rejected_records']} respinti")
                
                if validation_results['rejection_reasons']:
                    print(f"   ️ Rejection reasons: {', '.join(validation_results['rejection_reasons'])}")
                    all_rejection_reasons.extend(validation_results['rejection_reasons'])
                
                # Auto-recovery: se rejection > 10% e source era YF, prova altre fonti
                if (source_used == 'YF' and 
                    validation_results['rejected_records'] > 0 and 
                    validation_results['rejected_records'] / validation_results['total_records'] > 0.10):
                    
                    print(f"    Alta rejection rate ({validation_results['coverage_pct']:.1f}% coverage), tento fonti alternative...")
                    
                    # Prova fonti alternative in ordine
                    for alt_source in ['Stooq', 'Investing.com', 'CSV Manual']:
                        alt_data = None
                        
                        if alt_source == 'Stooq':
                            alt_data = download_stooq_data(symbol, start_date, end_date)
                        elif alt_source == 'Investing.com':
                            alt_data = download_investing_com_data(symbol, start_date, end_date)
                        elif alt_source == 'CSV Manual':
                            alt_data = load_manual_csv_data(symbol, start_date, end_date)
                        
                        if alt_data is not None and not alt_data.empty:
                            alt_validation, alt_valid = validate_data_quality(alt_data, symbol)
                            
                            if alt_validation['coverage_pct'] > validation_results['coverage_pct']:
                                print(f"    {alt_source} migliore: {alt_validation['coverage_pct']:.1f}% vs {validation_results['coverage_pct']:.1f}%")
                                valid_df = alt_valid
                                validation_results = alt_validation
                                source_used = alt_source
                                all_rejection_reasons.append(f"Auto-recovery: used {alt_source} for {symbol}")
                                break
                
                # Insert in staging table
                if not valid_df.empty:
                    # Prepara dati per staging
                    staging_df = valid_df.reset_index()
                    staging_df['symbol'] = symbol
                    staging_df['source'] = source_used
                    
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
                    
                    print(f"    {symbol}: {len(valid_df)} record inseriti in market_data")
                
                total_accepted += validation_results['accepted_records']
                total_rejected += validation_results['rejected_records']
                
            except Exception as e:
                print(f"    Errore processamento {symbol}: {e}")
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
        
        # Post-ingestion quality metrics
        print(f"\n Ingestion completata!")
        print(f" Totali: {total_accepted} record accettati, {total_rejected} record respinti")
        
        if total_accepted + total_rejected > 0:
            overall_coverage = (total_accepted / (total_accepted + total_rejected)) * 100
            print(f" Coverage globale: {overall_coverage:.1f}%")
        
        # Gap analysis per simbolo
        print(f"\n Gap Analysis:")
        for symbol in symbols:
            gap_info = analyze_gaps(conn, symbol, start_date_override or (end_date - timedelta(days=365)), end_date)
            print(f"   {symbol}: {gap_info['actual_days']}/{gap_info['expected_days']} giorni ({gap_info['coverage_pct']:.1f}% coverage, {gap_info['missing_days']} gap)")
        
        print(f"\n Run ID: {run_id}")
        
        return True
        
    except Exception as e:
        print(f" Errore ingestion: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ingestione dati - ETF Italia Project')
    parser.add_argument('--start-date', type=str, default=None, help='Data inizio (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None, help='Data fine (YYYY-MM-DD)')
    parser.add_argument('--initial-start-date', type=str, default=None, help='Start date di default per simboli nuovi (YYYY-MM-DD). Se omesso usa config.initial_start_date o 2010-01-01')
    parser.add_argument('--full-refresh', action='store_true', help='Reingest completa per simbolo (cancella market_data per symbol)')
    parser.add_argument('--symbol', action='append', default=None,
                        help='Processa solo questo simbolo (ripetibile). Esempio: --symbol CSSPX.MI')
    parser.add_argument('--symbols', type=str, default=None,
                        help='Lista simboli separati da virgola (alias di --symbol). Esempio: --symbols CSSPX.MI,EIMI.MI')


    # Operability gate (post-ingest): valuta completezza dati su universo e marca NOTRADE/NOOPERATIONS nel calendario
    parser.add_argument('--venue', type=str, default=os.environ.get('ETF_VENUE','XMIL'), help='Venue per trading_calendar (es. BIT o XMIL)')
    parser.add_argument('--post-operability-gate', action='store_true', help="Forza l'esecuzione di operability_gate.py a fine ingest")
    parser.add_argument('--no-post-operability-gate', action='store_true', help='Disabilita operability_gate.py post-ingest (default: attivo)')
    parser.add_argument('--warn-threshold', type=float, default=0.8, help='Soglia warning (>= warn e < 1.0 = operabile con warning)')
    parser.add_argument('--alert-threshold', type=float, default=0.5, help='Soglia alert (>= alert e < warn = alert; < alert = NOOPERATIONS)')
    parser.add_argument('--lookback-days', type=int, default=30, help='Giorni indietro da max_market_date da valutare nel gate')

    args = parser.parse_args()

    start_date_override = datetime.strptime(args.start_date, '%Y-%m-%d').date() if args.start_date else None
    end_date_override = datetime.strptime(args.end_date, '%Y-%m-%d').date() if args.end_date else None

    symbols_filter = []
    if getattr(args, 'symbol', None):
        symbols_filter.extend(args.symbol)
    if getattr(args, 'symbols', None):
        symbols_filter.extend([s.strip() for s in args.symbols.split(',') if s.strip()])
    if not symbols_filter:
        symbols_filter = None

    success = ingest_data(
        start_date_override=start_date_override,
        end_date_override=end_date_override,
        full_refresh=args.full_refresh,
        symbols_filter=symbols_filter,
        initial_start_date_override=args.initial_start_date,
    )

    # Post-operability gate (se richiesto)
    run_gate = success and (args.post_operability_gate or (not args.no_post_operability_gate))

    if run_gate:
        try:
            import subprocess
            import sys as _sys
            from pathlib import Path as _Path
            gate_script = _Path(__file__).resolve().parents[1] / 'quality' / 'operability_gate.py'
            cmd = [
                _sys.executable, str(gate_script),
                '--venue', args.venue,
                '--warn-threshold', str(args.warn_threshold),
                '--alert-threshold', str(args.alert_threshold),
                '--lookback-days', str(args.lookback_days),
                '--apply',
            ]
            print("\nPost-operability gate: " + " ".join(cmd))
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"⚠️  Post-operability gate fallito (non bloccante): {e}")

    sys.exit(0 if success else 1)
