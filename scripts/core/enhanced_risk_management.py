#!/usr/bin/env python3
"""
Enhanced Risk Management - ETF Italia Project v10
Corrections for -59% drawdown and zombie price guardrails
"""

import sys
import os
import json
import duckdb
import numpy as np
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def enhanced_risk_management():
    """Implementa correzioni rischio aggressive per drawdown e zombie prices"""
    
    print("🛡️ ENHANCED RISK MANAGEMENT - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Aggressive Risk Scalar for High Volatility
        print("\n1️⃣ IMPLEMENTING AGGRESSIVE VOLATILITY RISK SCALAR")
        print("-" * 50)
        
        # Nuovi parametri aggressivi
        VOLATILITY_THRESHOLD_WARNING = 0.15  # 15%
        VOLATILITY_THRESHOLD_CRITICAL = 0.20  # 20%
        AGGRESSIVE_SCALAR_WARNING = 0.3      # 70% reduction at 15%
        AGGRESSIVE_SCALAR_CRITICAL = 0.1     # 90% reduction at 20%
        
        # Analizza volatilità corrente
        vol_analysis = conn.execute("""
        WITH current_vol AS (
            SELECT 
                rm.symbol,
                rm.volatility_20d,
                rm.adj_close,
                md.volume,
                LAG(rm.adj_close) OVER (PARTITION BY rm.symbol ORDER BY rm.date) as prev_close
            FROM risk_metrics rm
            LEFT JOIN market_data md ON rm.symbol = md.symbol AND rm.date = md.date
            WHERE rm.date = (SELECT MAX(date) FROM risk_metrics)
            AND rm.symbol IN ('CSSPX.MI', 'XS2L.MI')
        )
        SELECT 
            symbol,
            volatility_20d,
            adj_close,
            volume,
            prev_close,
            CASE 
                WHEN volatility_20d > ? THEN 'CRITICAL'
                WHEN volatility_20d > ? THEN 'WARNING'
                ELSE 'NORMAL'
            END as vol_regime,
            CASE 
                WHEN volatility_20d > ? THEN ?
                WHEN volatility_20d > ? THEN ?
                ELSE 1.0
            END as aggressive_scalar
        FROM current_vol
        """, [VOLATILITY_THRESHOLD_CRITICAL, VOLATILITY_THRESHOLD_WARNING, 
              VOLATILITY_THRESHOLD_CRITICAL, AGGRESSIVE_SCALAR_CRITICAL,
              VOLATILITY_THRESHOLD_WARNING, AGGRESSIVE_SCALAR_WARNING]).fetchall()
        
        print(f"   📊 Analisi volatilità aggressiva:")
        for symbol, vol, price, volume, prev_close, regime, scalar in vol_analysis:
            print(f"      {symbol}: vol {vol:.1%} → regime {regime} → scalar {scalar:.2f}")
            
            # Update risk scalar in signals table
            if regime != 'NORMAL':
                update_query = """
                UPDATE signals 
                SET risk_scalar = ? * risk_scalar,
                    explain_code = explain_code || '_AGGRESSIVE_VOL'
                WHERE symbol = ? 
                AND date = (SELECT MAX(date) FROM signals)
                """
                conn.execute(update_query, [scalar, symbol])
                print(f"         ✅ Risk scalar aggiornato per {symbol}")
        
        # 2. Zombie Price Detection
        print("\n2️⃣ DETECTING ZOMBIE PRICES (Illiquid ETFs)")
        print("-" * 50)
        
        # Definizione zombie price: stesso prezzo per 3+ giorni con volume 0
        zombie_detection = conn.execute("""
        WITH price_stability AS (
            SELECT 
                symbol,
                date,
                adj_close,
                volume,
                LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) as prev_close,
                LAG(adj_close, 2) OVER (PARTITION BY symbol ORDER BY date) as prev2_close,
                LAG(adj_close, 3) OVER (PARTITION BY symbol ORDER BY date) as prev3_close
            FROM market_data 
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY symbol, date DESC
        ),
        zombie_days AS (
            SELECT 
                symbol,
                date,
                adj_close,
                volume,
                CASE 
                    WHEN adj_close = prev_close AND prev_close = prev2_close AND prev2_close = prev3_close
                    AND volume = 0 AND prev_close IS NOT NULL
                    THEN 'ZOMBIE_3_DAYS'
                    WHEN adj_close = prev_close AND prev_close = prev2_close
                    AND volume = 0 AND prev_close IS NOT NULL
                    THEN 'ZOMBIE_2_DAYS'
                    ELSE 'ACTIVE'
                END as zombie_status
            FROM price_stability
        )
        SELECT 
            symbol,
            zombie_status,
            COUNT(*) as days_count,
            AVG(volume) as avg_volume,
            STDDEV(adj_close) as price_stddev
        FROM zombie_days
        GROUP BY symbol, zombie_status
        ORDER BY symbol, zombie_status
        """).fetchall()
        
        print(f"   🧟 Analisi zombie prices:")
        zombie_affected_symbols = []
        
        for symbol, status, count, avg_vol, price_std in zombie_detection:
            if 'ZOMBIE' in status:
                print(f"      {symbol}: {status} ({count} giorni) - vol medio: {avg_vol:.0f}")
                zombie_affected_symbols.append(symbol)
                
                # Applica zombie price guardrail
                if status == 'ZOMBIE_3_DAYS':
                    # Forza risk scalar a 0 per zombie prices
                    guardrail_query = """
                    UPDATE signals 
                    SET risk_scalar = 0.0,
                        explain_code = 'ZOMBIE_PRICE_GUARD_' || explain_code
                    WHERE symbol = ? 
                    AND date = (SELECT MAX(date) FROM signals)
                    """
                    conn.execute(guardrail_query, [symbol])
                    print(f"         🛑 ZOMBIE GUARD: Risk scalar = 0 per {symbol}")
        
        if not zombie_affected_symbols:
            print("      ✅ Nessun zombie price detected")
        
        # 3. Synthetic Volatility for Zombie Prices
        print("\n3️⃣ SYNTHETIC VOLATILITY FOR ZOMBIE PRICES")
        print("-" * 50)
        
        # Calcola volatilità sintetica basata su settore/market
        synthetic_vol_query = """
        WITH synthetic_vol_calc AS (
            SELECT 
                md.symbol,
                md.date,
                md.adj_close,
                md.volume,
                -- Se volume = 0 per 3+ giorni, applica volatilità sintetica
                CASE 
                    WHEN md.volume = 0 
                    AND LAG(md.volume) OVER (PARTITION BY md.symbol ORDER BY md.date) = 0
                    AND LAG(md.volume, 2) OVER (PARTITION BY md.symbol ORDER BY md.date) = 0
                    THEN 0.25  -- 25% synthetic vol for zombie prices
                    ELSE rm.volatility_20d
                END as adjusted_volatility
            FROM market_data md
            LEFT JOIN risk_metrics rm ON md.symbol = rm.symbol AND md.date = rm.date
            WHERE md.symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND md.date >= CURRENT_DATE - INTERVAL '10 days'
        )
        SELECT 
            symbol,
            AVG(adjusted_volatility) as avg_synthetic_vol,
            COUNT(CASE WHEN volume = 0 THEN 1 END) as zero_volume_days,
            COUNT(*) as total_days
        FROM synthetic_vol_calc
        GROUP BY symbol
        """
        
        synthetic_vol = conn.execute(synthetic_vol_query).fetchall()
        
        print(f"   📊 Volatilità sintetica:")
        for symbol, avg_vol, zero_days, total in synthetic_vol:
            pct_zero = zero_days / total * 100 if total > 0 else 0
            print(f"      {symbol}: vol sintetica {avg_vol:.1%} ({pct_zero:.0f}% giorni volume=0)")
            
            # Se alta percentuale di volume zero, aggiorna risk metrics
            if pct_zero > 50:
                update_vol_query = """
                UPDATE risk_metrics 
                SET volatility_20d = ?,
                    drawdown_pct = CASE WHEN drawdown_pct > -0.05 THEN -0.05 ELSE drawdown_pct END
                WHERE symbol = ? 
                AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = ?)
                """
                conn.execute(update_vol_query, [avg_vol, symbol, symbol])
                print(f"         ✅ Volatilità sintetica applicata per {symbol}")
        
        # 4. Enhanced Drawdown Protection
        print("\n4️⃣ ENHANCED DRAWDOWN PROTECTION")
        print("-" * 50)
        
        # XS2L specific protection per -59% drawdown storico
        xs2l_protection = conn.execute("""
        WITH xs2l_risk AS (
            SELECT 
                symbol,
                adj_close,
                sma_200,
                drawdown_pct,
                volatility_20d,
                CASE 
                    WHEN drawdown_pct < -0.15 THEN 'CRITICAL_DD'
                    WHEN drawdown_pct < -0.10 THEN 'WARNING_DD'
                    ELSE 'NORMAL'
                END as dd_status
            FROM risk_metrics 
            WHERE symbol = 'XS2L.MI'
            AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = 'XS2L.MI')
        )
        SELECT 
            symbol,
            drawdown_pct,
            dd_status,
            CASE 
                WHEN dd_status = 'CRITICAL_DD' THEN 0.0
                WHEN dd_status = 'WARNING_DD' THEN 0.2
                ELSE 1.0
            END as dd_protection_scalar
        FROM xs2l_risk
        """).fetchone()
        
        if xs2l_protection:
            symbol, dd_pct, dd_status, dd_scalar = xs2l_protection
            print(f"   📉 XS2L.MI drawdown protection:")
            print(f"      Drawdown: {dd_pct:.1%} → Status: {dd_status}")
            print(f"      Protection scalar: {dd_scalar:.2f}")
            
            if dd_status != 'NORMAL':
                protection_query = """
                UPDATE signals 
                SET risk_scalar = LEAST(risk_scalar, ?),
                    explain_code = CASE 
                        WHEN ? = 'CRITICAL_DD' THEN 'XS2L_CRITICAL_DD_GUARD'
                        WHEN ? = 'WARNING_DD' THEN 'XS2L_WARNING_DD_GUARD'
                        ELSE explain_code
                    END
                WHERE symbol = 'XS2L.MI'
                AND date = (SELECT MAX(date) FROM signals)
                """
                conn.execute(protection_query, [dd_scalar, dd_status, dd_status])
                print(f"         🛡️ XS2L drawdown protection applicata")
        
        # 5. Report finale
        print("\n5️⃣ ENHANCED RISK MANAGEMENT SUMMARY")
        print("-" * 50)
        
        final_signals = conn.execute("""
        SELECT 
            symbol,
            signal_state,
            risk_scalar,
            explain_code,
            volatility_20d
        FROM signals 
        WHERE date = (SELECT MAX(date) FROM signals)
        ORDER BY symbol
        """).fetchall()
        
        print(f"   📊 Signal finali con risk management enhanced:")
        for symbol, state, scalar, explain, vol in final_signals:
            emoji = "🟢" if state == "RISK_ON" else "🔴" if state == "RISK_OFF" else "🟡"
            risk_emoji = "⚠️" if scalar < 0.3 else "✅" if scalar < 0.7 else "🔥"
            print(f"      {emoji} {symbol}: {state} | scalar: {scalar:.3f} {risk_emoji}")
            print(f"         {explain} | vol: {vol:.1%}")
        
        # 6. Audit log
        audit_data = {
            'timestamp': datetime.now().isoformat(),
            'enhanced_risk_management': {
                'aggressive_volatility_thresholds': {
                    'warning': VOLATILITY_THRESHOLD_WARNING,
                    'critical': VOLATILITY_THRESHOLD_CRITICAL,
                    'warning_scalar': AGGRESSIVE_SCALAR_WARNING,
                    'critical_scalar': AGGRESSIVE_SCALAR_CRITICAL
                },
                'zombie_price_detection': {
                    'zombie_symbols': zombie_affected_symbols,
                    'zombie_days_count': len([s for s in zombie_detection if 'ZOMBIE' in s[1]])
                },
                'synthetic_volatility_applied': len([v for v in synthetic_vol if v[2] > 0]),
                'xs2l_protection': {
                    'status': xs2l_protection[2] if xs2l_protection else 'NORMAL',
                    'scalar_applied': float(xs2l_protection[3]) if xs2l_protection else 1.0
                },
                'final_signals': [
                    {
                        'symbol': s[0],
                        'state': s[1],
                        'scalar': float(s[2]),
                        'explain': s[3],
                        'volatility': float(s[4])
                    } for s in final_signals
                ]
            }
        }
        
        # Salva audit log
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            audit_file = sm.add_report_to_session('risk_management', audit_data, 'json')
            print(f"\n   📋 Audit log salvato: {audit_file}")
        except ImportError:
            print(f"\n   ⚠️ Session Manager non disponibile")
        
        print(f"\n✅ ENHANCED RISK MANAGEMENT COMPLETATO")
        print(f"   - Volatilità >15%: scalar ridotto del 70%")
        print(f"   - Volatilità >20%: scalar ridotto del 90%")
        print(f"   - Zombie prices: risk scalar = 0")
        print(f"   - XS2L drawdown: protezione aggressiva")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore enhanced risk management: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = enhanced_risk_management()
    sys.exit(0 if success else 1)
