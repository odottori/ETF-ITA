#!/usr/bin/env python3
"""
Compute Signals - ETF Italia Project v10
Signal Engine per generazione segnali oggettivi secondo DIPF §4
"""

import sys
import os
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def compute_signals():
    """Calcola segnali per universo ETF"""
    
    print("📊 COMPUTE SIGNALS - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        # 1. Setup Signal Engine
        print("🔧 Setup Signal Engine...")
        
        # Crea tabella signals se non esiste
        conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
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
        """)
        
        # Crea indici
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_date_symbol ON signals(date, symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_state ON signals(signal_state)")
        
        print("✅ Signal Engine ready")
        
        # 2. Ottieni simboli universe
        symbols = []
        symbols.extend([etf['symbol'] for etf in config['universe']['core']])
        symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
        
        print(f"📊 Processing symbols: {symbols}")
        
        # 3. Calcola segnali per ogni simbolo
        total_signals = 0
        
        for symbol in symbols:
            print(f"\n📈 Computing signals for {symbol}")
            
            # Ottieni dati recenti con metriche
            metrics_query = """
            SELECT 
                date,
                adj_close,
                sma_200,
                volatility_20d,
                drawdown_pct,
                daily_return
            FROM risk_metrics 
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT 60
            """
            
            df = conn.execute(metrics_query, [symbol]).fetchdf()
            
            if df.empty:
                print(f"   ⚠️ No data available for {symbol}")
                continue
            
            # Calcola segnali per ogni data
            signals_data = []
            
            for idx, row in df.iterrows():
                signal_date = row['date']
                current_price = row['adj_close']
                sma_200 = row['sma_200']
                volatility_20d = row['volatility_20d']
                drawdown_pct = row['drawdown_pct']
                
                # Inizializza variabili segnale
                signal_state = 'HOLD'
                risk_scalar = 1.0
                explain_code = 'NEUTRAL'
                spy_guard = False
                regime_filter = 'NEUTRAL'
                
                # 3.1 Trend Following Signal (SMA 200)
                if pd.notna(sma_200):
                    if current_price > sma_200 * 1.02:  # 2% above SMA
                        signal_state = 'RISK_ON'
                        explain_code = 'TREND_UP_SMA200'
                    elif current_price < sma_200 * 0.98:  # 2% below SMA
                        signal_state = 'RISK_OFF'
                        explain_code = 'TREND_DOWN_SMA200'
                
                # 3.2 Volatility Regime Filter
                if pd.notna(volatility_20d):
                    vol_threshold = config['risk_management']['volatility_breaker']
                    if volatility_20d > vol_threshold:
                        regime_filter = 'HIGH_VOL'
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 0.5  # Halve size in high vol
                            explain_code += '_VOL_ADJ'
                    elif volatility_20d < 0.10:
                        regime_filter = 'LOW_VOL'
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 1.2  # Increase size in low vol
                            explain_code += '_VOL_BOOST'
                
                # 3.3 Drawdown Protection
                if pd.notna(drawdown_pct):
                    if drawdown_pct < -0.15:  # 15% drawdown
                        signal_state = 'RISK_OFF'
                        explain_code = 'DRAWDOWN_PROTECT'
                        risk_scalar = 0.0
                    elif drawdown_pct < -0.10:  # 10% drawdown
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 0.7
                            explain_code += '_DD_ADJ'
                
                # 3.4 Spy Guard (per tutti i simboli)
                spy_guard_active = check_spy_guard(conn, signal_date, config)
                spy_guard = spy_guard_active
                
                if spy_guard_active:
                    if signal_state == 'RISK_ON':
                        signal_state = 'RISK_OFF'
                        explain_code = 'SPY_GUARD_BLOCK'
                        risk_scalar = 0.0
                    regime_filter = 'BEAR_MARKET'
                
                # 3.5 Risk Scalar Volatility Targeting
                target_vol = config['settings']['volatility_target']  # 15%
                if pd.notna(volatility_20d) and volatility_20d > 0:
                    vol_scalar = target_vol / volatility_20d
                    vol_scalar = min(1.0, vol_scalar)  # Cap at 1.0
                    vol_scalar = max(config['risk_management']['risk_scalar_floor'], vol_scalar)  # Floor
                    
                    risk_scalar *= vol_scalar
                
                # Arrotonda risk scalar
                risk_scalar = round(risk_scalar, 3)
                risk_scalar = max(0.0, min(1.0, risk_scalar))
                
                signals_data.append({
                    'date': signal_date,
                    'symbol': symbol,
                    'signal_state': signal_state,
                    'risk_scalar': risk_scalar,
                    'explain_code': explain_code,
                    'sma_200': sma_200,
                    'volatility_20d': volatility_20d,
                    'spy_guard': spy_guard,
                    'regime_filter': regime_filter
                })
            
            # Insert signals nel database
            if signals_data:
                # Pulisci signals esistenti per questo simbolo
                start_date = signals_data[0]['date']
                end_date = signals_data[-1]['date']
                conn.execute("""
                DELETE FROM signals 
                WHERE symbol = ? AND date BETWEEN ? AND ?
                """, [symbol, start_date, end_date])
                
                # Insert nuovi signals
                signals_to_insert = []
                for signal in signals_data:
                    signals_to_insert.append((
                        signal['date'],
                        signal['symbol'],
                        signal['signal_state'],
                        signal['risk_scalar'],
                        signal['explain_code'],
                        signal['sma_200'],
                        signal['volatility_20d'],
                        signal['spy_guard'],
                        signal['regime_filter'],
                        datetime.now()
                    ))
                
                conn.executemany("""
                INSERT INTO signals (date, symbol, signal_state, risk_scalar, explain_code, sma_200, volatility_20d, spy_guard, regime_filter, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, signals_to_insert)
                
                print(f"   ✅ {symbol}: {len(signals_data)} signals computed")
                total_signals += len(signals_data)
        
        # 4. Report segnali correnti
        print(f"\n📊 CURRENT SIGNALS SNAPSHOT")
        print("-" * 40)
        
        current_signals_query = """
        SELECT symbol, signal_state, risk_scalar, explain_code, 
               sma_200, volatility_20d, spy_guard, regime_filter
        FROM signals 
        WHERE date = (SELECT MAX(date) FROM signals)
        ORDER BY symbol
        """
        
        current_signals = conn.execute(current_signals_query).fetchall()
        
        for signal in current_signals:
            symbol, state, scalar, explain, sma, vol, spy_guard, regime = signal
            
            emoji = "🟢" if state == "RISK_ON" else "🔴" if state == "RISK_OFF" else "🟡"
            guard_emoji = "🛡️" if spy_guard else ""
            
            print(f"{emoji} {symbol}: {state} (scalar: {scalar:.3f}) {guard_emoji}")
            print(f"   📝 {explain} | Vol: {vol:.1%} | Regime: {regime}")
        
        # 5. Summary statistics
        print(f"\n📈 SIGNALS SUMMARY")
        print("-" * 40)
        
        summary_query = """
        SELECT 
            signal_state,
            COUNT(*) as count,
            AVG(risk_scalar) as avg_scalar
        FROM signals 
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY signal_state
        """
        
        summary = conn.execute(summary_query).fetchall()
        
        for state, count, avg_scalar in summary:
            emoji = "🟢" if state == "RISK_ON" else "🔴" if state == "RISK_OFF" else "🟡"
            print(f"{emoji} {state}: {count} signals (avg scalar: {avg_scalar:.3f})")
        
        print(f"\n🎉 SIGNALS COMPUTATION COMPLETED")
        print(f"📊 Total signals processed: {total_signals}")
        
        # Commit transazione
        conn.commit()
        
        return True
        
    except Exception as e:
        print(f"❌ Errore compute signals: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

def check_spy_guard(conn, date, config):
    """Verifica Spy Guard per data specifica"""
    
    if not config['risk_management']['spy_guard_enabled']:
        return False
    
    try:
        # Ottieni S&P 500 SMA 200
        spy_query = """
        SELECT adj_close, sma_200
        FROM risk_metrics 
        WHERE symbol = '^GSPC' AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """
        
        spy_data = conn.execute(spy_query, [date]).fetchone()
        
        if spy_data and spy_data[1] is not None:
            spy_close, spy_sma = spy_data
            return spy_close < spy_sma  # Bear market if below SMA 200
        
    except Exception:
        pass
    
    return False

if __name__ == "__main__":
    success = compute_signals()
    sys.exit(0 if success else 1)
