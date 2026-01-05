#!/usr/bin/env python3
"""
Spike Detector - ETF Italia Project v10
P0.4: Spike threshold per simbolo con audit soglia
"""

import sys
import os
import duckdb
from datetime import datetime
import numpy as np

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def detect_spikes():
    """Rileva spike anomali con threshold dinamico per simbolo"""
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    print("📈 P0.4: Spike Threshold Detection")
    print("=" * 50)
    
    try:
        # Test 1: Calcolo threshold dinamici per simbolo
        print("1️⃣ Calcolo threshold dinamici...")
        
        # Calcola volatilità storica per ogni simbolo
        volatility_data = conn.execute("""
        SELECT 
            symbol,
            STDDEV(daily_return) * SQRT(252) as annual_vol,
            AVG(daily_return) as avg_daily_ret,
            COUNT(*) as days
        FROM (
            SELECT 
                symbol,
                date,
                (close / LAG(close) OVER (PARTITION BY symbol ORDER BY date) - 1) as daily_return
            FROM market_data 
            WHERE date >= '2020-01-01'
        ) daily_returns
        GROUP BY symbol
        """).fetchall()
        
        # Definisci threshold basati su volatilità (3 sigma)
        spike_thresholds = {}
        for symbol, vol, avg_ret, days in volatility_data:
            # Threshold = 3 * volatilità giornaliera
            daily_vol = vol / np.sqrt(252)
            threshold = 3 * daily_vol
            spike_thresholds[symbol] = {
                'annual_vol': vol,
                'daily_vol': daily_vol,
                'threshold': threshold,
                'days_analyzed': days
            }
        
        print(f"   📊 Threshold calcolati per {len(spike_thresholds)} simboli:")
        for symbol, data in spike_thresholds.items():
            print(f"      {symbol}: vol={data['annual_vol']:.3f}, threshold={data['threshold']:.3f}")
        
        # Test 2: Rilevazione spike
        print("2️⃣ Rilevazione spike anomali...")
        
        all_spikes = []
        for symbol, threshold_data in spike_thresholds.items():
            threshold = threshold_data['threshold']
            
            spikes = conn.execute("""
            SELECT 
                date,
                close,
                prev_close,
                daily_return,
                ? as threshold_used
            FROM (
                SELECT 
                    date,
                    close,
                    LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close,
                    (close / LAG(close) OVER (PARTITION BY symbol ORDER BY date) - 1) as daily_return
                FROM market_data 
                WHERE symbol = ? AND date >= '2020-01-01'
            ) symbol_data
            WHERE ABS(daily_return) > ?
            ORDER BY ABS(daily_return) DESC
            LIMIT 10
            """, [threshold, symbol, threshold]).fetchall()
            
            if spikes:
                print(f"   🚨 {symbol}: {len(spikes)} spike rilevati (threshold={threshold:.3f})")
                for date, close, prev_close, ret, thr in spikes[:3]:  # Top 3
                    print(f"      {date}: {ret:.4f} ({close:.2f}/{prev_close:.2f})")
                    all_spikes.append({
                        'symbol': symbol,
                        'date': str(date),
                        'return': ret,
                        'close': close,
                        'prev_close': prev_close,
                        'threshold_used': thr
                    })
        
        # Test 3: Audit log spike detection
        print("3️⃣ Generazione audit log spike detection...")
        
        # Statistiche spike
        spike_stats = {}
        for symbol, data in spike_thresholds.items():
            symbol_spikes = [s for s in all_spikes if s['symbol'] == symbol]
            spike_stats[symbol] = {
                'total_spikes': len(symbol_spikes),
                'max_spike': max([abs(s['return']) for s in symbol_spikes]) if symbol_spikes else 0,
                'threshold_used': data['threshold'],
                'volatility': data['annual_vol']
            }
        
        audit_data = {
            'timestamp': datetime.now().isoformat(),
            'test_p0_4_spike_detection': {
                'symbols_analyzed': len(spike_thresholds),
                'total_spikes_detected': len(all_spikes),
                'spike_thresholds': spike_thresholds,
                'spike_statistics': spike_stats,
                'top_spikes': sorted(all_spikes, key=lambda x: abs(x['return']), reverse=True)[:10]
            }
        }
        
        # Salva audit log
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            audit_file = sm.add_report_to_session('analysis', audit_data, 'json')
            print(f"   📋 Audit log salvato: {audit_file}")
        except ImportError:
            print("   ⚠️ Session Manager non disponibile, audit non salvato")
        
        # Verdict finale
        if len(all_spikes) == 0:
            print("\n🎉 P0.4 COMPLETATO: Nessuno spike anomalo rilevato")
            return True
        else:
            print(f"\n⚠️ P0.4 COMPLETATO: {len(all_spikes)} spike rilevati con threshold dinamici")
            return True
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = detect_spikes()
    sys.exit(0 if success else 1)
