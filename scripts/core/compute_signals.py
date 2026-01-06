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
from itertools import chain

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def compute_signals():
    """Calcola segnali per universo ETF"""
    
    print(" COMPUTE SIGNALS - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        # 1. Setup Signal Engine
        print(" Setup Signal Engine...")
        
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
        
        print(" Signal Engine ready")
        
        # 2. Ottieni simboli universe
        symbols = []
        symbols.extend([etf['symbol'] for etf in config['universe']['core']])
        symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
        
        # Aggiungi bond se presenti (per diversificazione operativa)
        if 'bond' in config['universe']:
            bond_symbols = [etf['symbol'] for etf in config['universe']['bond']]
            symbols.extend(bond_symbols)
            print(f" Bond symbols added: {bond_symbols}")
        
        print(f" Processing symbols: {symbols}")
        
        # 3. Calcola segnali per ogni simbolo
        total_signals = 0
        
        for symbol in symbols:
            print(f"\n Computing signals for {symbol}")
            
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
                print(f"   ️ No data available for {symbol}")
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
                
                # 3.5 Entry-Aware Stop-Loss Check (after trend but before other filters)
                entry_price = check_position_entry_price(conn, symbol, signal_date)
                if entry_price:
                    stop_action, stop_reason = check_entry_aware_stop_loss(config, symbol, current_price, entry_price, volatility_20d)
                    if stop_action:
                        signal_state = stop_action
                        explain_code = stop_reason
                        risk_scalar = 0.0
                        print(f"    🛑 Entry-aware stop-loss: {stop_reason}")

                # 3.6 Volatility Regime Filter
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
                
                # 3.7 Drawdown Protection
                if pd.notna(drawdown_pct):
                    if drawdown_pct < -0.15:  # 15% drawdown
                        signal_state = 'RISK_OFF'
                        explain_code = 'DRAWDOWN_PROTECT'
                        risk_scalar = 0.0
                    elif drawdown_pct < -0.10:  # 10% drawdown
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 0.7
                            explain_code += '_DD_ADJ'
                
                # 3.8 Spy Guard (per tutti i simboli)
                spy_guard_active = check_spy_guard(conn, signal_date, config)
                spy_guard = spy_guard_active
                
                if spy_guard_active:
                    if signal_state == 'RISK_ON':
                        signal_state = 'RISK_OFF'
                        explain_code = 'SPY_GUARD_BLOCK'
                        risk_scalar = 0.0
                    regime_filter = 'BEAR_MARKET'
                
                # 3.9 Risk Scalar Volatility Targeting
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
            
            # Insert signals nel database con UPSERT
            if signals_data:
                # Ottieni prossimo ID disponibile per evitare conflitti
                next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM signals").fetchone()[0]
                
                # Usa UPSERT di DuckDB (INSERT OR REPLACE)
                signals_to_insert = []
                for i, signal in enumerate(signals_data):
                    signals_to_insert.append((
                        next_id + i,  # ID esplicito
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
                
                # Usa INSERT OR REPLACE per gestire duplicati automaticamente
                conn.executemany("""
                INSERT OR REPLACE INTO signals (id, date, symbol, signal_state, risk_scalar, explain_code, sma_200, volatility_20d, spy_guard, regime_filter, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, signals_to_insert)
                
                print(f"    {symbol}: {len(signals_data)} signals upserted")
                total_signals += len(signals_data)
        
        # 4. Report segnali correnti
        print(f"\n CURRENT SIGNALS SNAPSHOT")
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
            
            emoji = "" if state == "RISK_ON" else "" if state == "RISK_OFF" else ""
            guard_emoji = "️" if spy_guard else ""
            
            print(f"{emoji} {symbol}: {state} (scalar: {scalar:.3f}) {guard_emoji}")
            print(f"    {explain} | Vol: {vol:.1%} | Regime: {regime}")
        
        # 5. Summary statistics
        print(f"\n SIGNALS SUMMARY")
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
            emoji = "" if state == "RISK_ON" else "" if state == "RISK_OFF" else ""
            print(f"{emoji} {state}: {count} signals (avg scalar: {avg_scalar:.3f})")
        
        print(f"\n SIGNALS COMPUTATION COMPLETED")
        print(f" Total signals processed: {total_signals}")
        
        # Commit transazione
        conn.commit()
        
        return True
        
    except Exception as e:
        print(f" Errore compute signals: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

def check_position_entry_price(conn, symbol, date):
    """Ottiene prezzo di entrata per posizione esistente"""
    try:
        entry_query = """
        SELECT AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price
        FROM fiscal_ledger 
        WHERE symbol = ? 
        AND type IN ('BUY', 'SELL')
        AND date <= ?
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        """
        result = conn.execute(entry_query, [symbol, date]).fetchone()
        return result[0] if result and result[0] else None
    except Exception:
        return None

def check_entry_aware_stop_loss(config, symbol, current_price, entry_price, volatility_20d):
    """Verifica stop-loss entry-aware basato su prezzo di entrata"""
    if entry_price is None or entry_price <= 0:
        return None, None
    
    # PnL percentage from entry
    pnl_pct = (current_price - entry_price) / entry_price
    
    # Get appropriate stop-loss based on symbol type
    if symbol == 'XS2L.MI':
        stop_loss = config['risk_management'].get('xs2l_stop_loss', -0.15)
        trailing_stop = config['risk_management'].get('xs2l_trailing_stop', -0.10)
    else:
        stop_loss = config['risk_management'].get('stop_loss_satellite', -0.15)
        trailing_stop = config['risk_management'].get('trailing_stop_satellite', -0.10)
    
    # Adjust stop-loss based on volatility (more volatile = wider stop)
    if volatility_20d and volatility_20d > 0.2:  # High volatility
        stop_loss *= 1.5  # 50% wider stop
        trailing_stop *= 1.5
    
    # Check stop-loss
    if pnl_pct <= stop_loss:
        return 'RISK_OFF', f'STOP_LOSS_ENTRY_{pnl_pct:.1%}'
    
    # Check trailing stop
    if pnl_pct <= trailing_stop:
        return 'RISK_OFF', f'TRAILING_STOP_ENTRY_{pnl_pct:.1%}'
    
    return None, None

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
