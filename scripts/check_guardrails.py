#!/usr/bin/env python3
"""
Check Guardrails - ETF Italia Project v10
Validazione guardrails e risk management
"""

import sys
import os
import json
import duckdb
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_guardrails():
    """Verifica guardrails e risk management"""
    
    print("🛡️ CHECK GUARDRAILS - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        guardrails_status = {
            'overall_status': 'SAFE',
            'warnings': [],
            'alerts': [],
            'recommendations': []
        }
        
        print("🔍 Verifica guardrails...")
        
        # 1. Volatility Breaker
        print("\n📊 Volatility Breaker Check:")
        
        vol_breaker = config['risk_management']['volatility_breaker']
        
        high_vol_symbols = conn.execute("""
        SELECT symbol, volatility_20d
        FROM risk_metrics 
        WHERE date = (SELECT MAX(date) FROM risk_metrics)
          AND volatility_20d > ?
          AND symbol IN (SELECT DISTINCT symbol FROM signals WHERE date >= CURRENT_DATE - INTERVAL '30 days')
        ORDER BY volatility_20d DESC
        """, [vol_breaker]).fetchall()
        
        if high_vol_symbols:
            print(f"⚠️ HIGH VOLATILITY ALERT (> {vol_breaker:.0%}):")
            for symbol, vol in high_vol_symbols:
                print(f"  {symbol}: {vol:.1%}")
                guardrails_status['alerts'].append(f"High volatility: {symbol} {vol:.1%}")
            
            if len(high_vol_symbols) >= 2:
                guardrails_status['overall_status'] = 'DANGER'
                guardrails_status['recommendations'].append("Consider reducing position sizing in high volatility regime")
        else:
            print("✅ Volatility within acceptable range")
        
        # 2. Spy Guard Check
        print(f"\n🛡️ Spy Guard Check:")
        
        spy_guard_enabled = config['risk_management']['spy_guard_enabled']
        
        if spy_guard_enabled:
            # Ottieni S&P 500 status
            spy_data = conn.execute("""
            SELECT adj_close, sma_200
            FROM risk_metrics 
            WHERE symbol = '^GSPC' AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = '^GSPC')
            """).fetchone()
            
            if spy_data and spy_data[0] < spy_data[1]:
                print(f"⚠️ SPY GUARD ACTIVE (S&P 500 < SMA 200)")
                print(f"  S&P 500: €{spy_data[0]:.2f} | SMA 200: €{spy_data[1]:.2f}")
                print(f"  Ratio: {spy_data[0]/spy_data[1]:.3f}")
                
                guardrails_status['alerts'].append("Spy Guard active - bear market detected")
                guardrails['recommendations'].append("Consider defensive positioning or cash allocation")
                
                # Controlla segnali RISK_ON
                risk_on_signals = conn.execute("""
                SELECT COUNT(*) FROM signals 
                WHERE signal_state = 'RISK_ON' 
                  AND date >= CURRENT_DATE - INTERVAL '7 days'
                """).fetchone()[0]
                
                if risk_on_signals > 0:
                    guardrails_status['overall_status'] = 'DANGER'
                    print(f"⚠️ {risk_on_signals} RISK_ON signals despite Spy Guard")
                    guardrails['recommendations'].append("Review signal logic - Spy Guard should override RISK_ON")
            else:
                print("✅ Spy Guard OK (S&P 500 > SMA 200)")
        else:
            print("ℹ️ Spy Guard disabled")
        
        # 3. Risk Scalar Floor Check
        print(f"\n📏 Risk Scalar Floor Check:")
        
        risk_floor = config['risk_management']['risk_scalar_floor']
        
        low_risk_signals = conn.execute("""
        SELECT symbol, risk_scalar
        FROM signals 
        WHERE date = (SELECT MAX(date) FROM signals)
          AND risk_scalar < ?
          AND signal_state = 'RISK_ON'
        """, [risk_floor]).fetchall()
        
        if low_risk_signals:
            print(f"⚠️ LOW RISK SCALAR (< {risk_floor:.1f}):")
            for symbol, scalar in low_risk_signals:
                print(f"  {symbol}: {scalar:.3f}")
                guardrails_status['warnings'].append(f"Low risk scalar: {symbol} {scalar:.3f}")
        else:
            print("✅ Risk scalars above minimum threshold")
        
        # 4. Position Concentration Check
        print(f"\n📊 Position Concentration Check:")
        
        positions = conn.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
            SUM(CASE WHEN type = 'BUY' THEN qty * price ELSE -qty * price END) as position_value
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        """).fetchall()
        
        if positions:
            total_value = sum(pos[2] for pos in positions)
            
            for symbol, qty, value in positions:
                concentration = value / total_value if total_value > 0 else 0
                if concentration > 0.4:  # 40% max allocation
                    print(f"⚠️ HIGH CONCENTRATION: {symbol}: {concentration:.1%}")
                    guardrails_status['warnings'].append(f"High concentration: {symbol} {concentration:.1%}")
        
            max_concentration = max(pos[2] / total_value if total_value > 0 else 0 for pos in positions)
            if max_concentration > 0.6:
                guardrails_status['overall_status'] = 'DANGER'
                guardrails['recommendations'].append("Consider rebalancing to reduce concentration risk")
        else:
            print("✅ No positions to check")
        
        # 5. Drawdown Check
        print(f"\n📉 Drawdown Check:")
        
        drawdown_data = conn.execute("""
        SELECT symbol, drawdown_pct
        FROM risk_metrics 
        WHERE date = (SELECT MAX(date) FROM risk_metrics)
          AND symbol IN (SELECT DISTINCT symbol FROM signals)
          AND drawdown_pct < -0.1
        ORDER BY drawdown_pct
        """).fetchall()
        
        if drawdown_data:
            print(f"⚠️ SIGNIFICANT DRAWDOWNS (< -10%):")
            for symbol, dd in drawdown_data:
                print(f"  {symbol}: {dd:.1%}")
                if dd < -0.2:
                    guardrails_status['alerts'].append(f"Severe drawdown: {symbol} {dd:.1%}")
                    guardrails_status['recommendations'].append(f"Consider reducing {symbol} exposure")
        else:
            print("✅ No significant drawdowns detected")
        
        # 6. Recent Signal Changes
        print(f"\n🔄 Recent Signal Changes:")
        
        signal_changes = conn.execute("""
        WITH signal_changes AS (
            SELECT 
                symbol,
                date,
                signal_state,
                LAG(signal_state) OVER (PARTITION BY symbol ORDER BY date) as prev_state
            FROM signals 
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        )
        SELECT symbol, COUNT(*) as changes
        FROM signal_changes 
        WHERE prev_state IS NOT NULL AND signal_state != prev_state
        GROUP BY symbol
        ORDER BY changes DESC
        """).fetchall()
        
        if signal_changes:
            print(f"⚠️ FREQUENT SIGNAL CHANGES (last 7 days):")
            for symbol, changes in signal_changes:
                print(f"  {symbol}: {changes} changes")
                if changes > 3:
                    guardrails_status['warnings'].append(f"Frequent signal changes: {symbol} {changes} changes")
                    guardrails['recommendations'].append(f"Review signal logic for {symbol}")
        else:
            print("✅ Stable signals")
        
        # 7. Overall Assessment
        print(f"\n🎯 GUARDRAILS ASSESSMENT:")
        print(f"Overall Status: {guardrails_status['overall_status']}")
        
        if guardrails_status['alerts']:
            print(f"\n🚨 ALERTS ({len(guardrails_status['alerts'])}):")
            for alert in guardrails_status['alerts']:
                print(f"  • {alert}")
        
        if guardrails_status['warnings']:
            print(f"\n⚠️ WARNINGS ({len(guardrails_status['warnings'])}):")
            for warning in guardrails_status['warnings']:
                print(f"  • {warning}")
        
        if guardrails_status['recommendations']:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in guardrails_status['recommendations']:
                print(f"  • {rec}")
        
        # 8. Save guardrails report
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        guardrails_file = os.path.join(reports_dir, f"guardrails_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(guardrails_file, 'w') as f:
            json.dump(guardrails_status, f, indent=2)
        
        print(f"\n📄 Guardrails report salvato: {guardrails_file}")
        
        # 9. Return status
        return guardrails_status['overall_status'] == 'SAFE'
        
    except Exception as e:
        print(f"❌ Errore check guardrails: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = check_guardrails()
    sys.exit(0 if success else 1)
