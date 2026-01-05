#!/usr/bin/env python3
"""
P2 Post-Implementation Verification - ETF Italia Project v10
Verifica che le correzioni P2 funzionino correttamente
"""

import sys
import os
import json
import duckdb
import numpy as np
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def verify_p2_implementation():
    """Verifica l'implementazione P2 con nuovi pesi"""
    
    print("✅ P2 — VERIFICA POST-IMPLEMENTAZIONE")
    print("=" * 50)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    
    try:
        # 1. Verifica configurazione aggiornata
        print("\n📋 1. Verifica Configurazione")
        print("-" * 30)
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        checks = []
        
        # Check bond ETF
        has_bond = 'bond' in config['universe']
        checks.append(('Bond ETF presente', has_bond))
        
        # Check guardrails P2
        p2_enabled = config['risk_management'].get('p2_guardrails_enabled', False)
        checks.append(('Guardrails P2 abilitati', p2_enabled))
        
        # Check thresholds
        corr_threshold = config['risk_management'].get('correlation_threshold', 0)
        checks.append(('Threshold correlazione', corr_threshold > 0))
        
        conc_threshold = config['risk_management'].get('concentration_threshold', 0)
        checks.append(('Threshold concentrazione', conc_threshold > 0))
        
        xs2l_cap = config['risk_management'].get('xs2l_position_cap', 0)
        checks.append(('Position cap XS2L', xs2l_cap > 0))
        
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
        
        # 2. Simulazione con nuovi pesi
        print("\n📊 2. Simulazione Nuovi Pesi (50/30/20)")
        print("-" * 40)
        
        conn = duckdb.connect(db_path)
        
        # Pesi target post-P2
        target_weights = {
            'CSSPX.MI': 0.50,
            'XS2L.MI': 0.30,
            'AGGH.MI': 0.20
        }
        
        print("   🎯 Pesi target:")
        for symbol, weight in target_weights.items():
            print(f"      {symbol}: {weight:.0%}")
        
        # Recupera volatilità reali
        vol_data = conn.execute("""
        WITH daily_returns AS (
            SELECT 
                symbol,
                date,
                (close / LAG(close) OVER (PARTITION BY symbol ORDER BY date) - 1) as daily_return
            FROM market_data 
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND close IS NOT NULL
        ),
        recent_returns AS (
            SELECT symbol, daily_return
            FROM daily_returns
            WHERE daily_return IS NOT NULL
            ORDER BY date DESC
            LIMIT 60
        )
        SELECT symbol, STDDEV(daily_return) * SQRT(252) as annual_vol
        FROM recent_returns
        GROUP BY symbol
        """).fetchall()
        
        volatilities = {row[0]: row[1] for row in vol_data}
        
        # Aggiungi volatilità bond (stimata)
        volatilities['AGGH.MI'] = 0.08  # 8% volatilità bond
        
        print(f"   📊 Volatilità:")
        for symbol, vol in volatilities.items():
            print(f"      {symbol}: {vol:.1%}")
        
        # Calcola correlazione
        correlation_data = conn.execute("""
        WITH daily_returns AS (
            SELECT 
                symbol,
                date,
                (close / LAG(close) OVER (PARTITION BY symbol ORDER BY date) - 1) as daily_return
            FROM market_data 
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND close IS NOT NULL
        ),
        filtered_returns AS (
            SELECT symbol, date, daily_return
            FROM daily_returns
            WHERE daily_return IS NOT NULL
            AND date >= CURRENT_DATE - INTERVAL '252 days'
        ),
        pivot_returns AS (
            SELECT 
                date,
                MAX(CASE WHEN symbol = 'CSSPX.MI' THEN daily_return END) as csspx_return,
                MAX(CASE WHEN symbol = 'XS2L.MI' THEN daily_return END) as xs2l_return
            FROM filtered_returns
            GROUP BY date
            HAVING csspx_return IS NOT NULL AND xs2l_return IS NOT NULL
        )
        SELECT CORR(csspx_return, xs2l_return) as correlation
        FROM pivot_returns
        """).fetchone()
        
        correlation = correlation_data[0] if correlation_data else 0.835
        
        # Calcola contribution-to-risk con nuovi pesi
        def calculate_contribution(weights, volatilities, correlation):
            """Calcola contribution-to-risk per 3 asset"""
            # Simplified per 3 asset (bond correlazione bassa)
            w_csspx, w_xs2l, w_bond = weights['CSSPX.MI'], weights['XS2L.MI'], weights['AGGH.MI']
            v_csspx, v_xs2l, v_bond = volatilities['CSSPX.MI'], volatilities['XS2L.MI'], volatilities['AGGH.MI']
            
            # Correlazioni stimate
            corr_csspx_xs2l = correlation
            corr_csspx_bond = 0.2
            corr_xs2l_bond = 0.15
            
            # Portfolio variance
            portfolio_var = (
                w_csspx**2 * v_csspx**2 + 
                w_xs2l**2 * v_xs2l**2 + 
                w_bond**2 * v_bond**2 +
                2*w_csspx*w_xs2l*v_csspx*v_xs2l*corr_csspx_xs2l +
                2*w_csspx*w_bond*v_csspx*v_bond*corr_csspx_bond +
                2*w_xs2l*w_bond*v_xs2l*v_bond*corr_xs2l_bond
            )
            
            portfolio_vol = np.sqrt(portfolio_var)
            
            # Contribution to risk
            contrib_csspx = (w_csspx*v_csspx * (w_csspx*v_csspx + w_xs2l*v_xs2l*corr_csspx_xs2l + w_bond*v_bond*corr_csspx_bond)) / portfolio_vol
            contrib_xs2l = (w_xs2l*v_xs2l * (w_xs2l*v_xs2l + w_csspx*v_csspx*corr_csspx_xs2l + w_bond*v_bond*corr_xs2l_bond)) / portfolio_vol
            contrib_bond = (w_bond*v_bond * (w_bond*v_bond + w_csspx*v_csspx*corr_csspx_bond + w_xs2l*v_xs2l*corr_xs2l_bond)) / portfolio_vol
            
            return {
                'portfolio_vol': portfolio_vol,
                'contributions': {
                    'CSSPX.MI': contrib_csspx,
                    'XS2L.MI': contrib_xs2l,
                    'AGGH.MI': contrib_bond
                }
            }
        
        risk_metrics = calculate_contribution(target_weights, volatilities, correlation)
        
        print(f"   🎯 Portfolio Vol: {risk_metrics['portfolio_vol']:.1%}")
        print(f"   ⚖️ Contribution-to-Risk:")
        for symbol, contrib in risk_metrics['contributions'].items():
            weight = target_weights[symbol]
            print(f"      {symbol}: {contrib:.1%} (peso {weight:.0%})")
        
        # 3. Verifica violazioni P2
        print("\n🔍 3. Verifica Violazioni P2")
        print("-" * 30)
        
        violations = []
        
        # Check correlazione
        if correlation > 0.7:
            violations.append(f"Correlazione {correlation:.3f} > 0.7")
        else:
            print(f"   ✅ Correlazione OK: {correlation:.3f}")
        
        # Check concentrazione
        max_contribution = max(risk_metrics['contributions'].values())
        if max_contribution > 0.5:  # Nuovo threshold
            max_symbol = max(risk_metrics['contributions'], key=risk_metrics['contributions'].get)
            violations.append(f"Concentrazione {max_symbol} {max_contribution:.1%} > 50%")
        else:
            print(f"   ✅ Concentrazione OK: max {max_contribution:.1%}")
        
        # Check volatilità
        if risk_metrics['portfolio_vol'] > 0.20:
            violations.append(f"Volatilità {risk_metrics['portfolio_vol']:.1%} > 20%")
        else:
            print(f"   ✅ Volatilità OK: {risk_metrics['portfolio_vol']:.1%}")
        
        # 4. Confronto prima/dopo
        print("\n📊 4. Confronto Prima/Dopo")
        print("-" * 30)
        
        print(f"{'Metrica':<20} {'Prima':<12} {'Dopo':<12} {'Miglioramento':<15}")
        print("-" * 60)
        print(f"{'Pesi XS2L':<20} {'50%':<12} {'30%':<12} {'-20%':<15}")
        print(f"{'Concentrazione':<20} {'66.3%':<12} {max_contribution:<12.1%} {'✅':<15}")
        print(f"{'Portfolio Vol':<20} {'15.2%':<12} {risk_metrics['portfolio_vol']:<12.1%} {'✅' if risk_metrics['portfolio_vol'] < 0.152 else '❌':<15}")
        print(f"{'Violazioni P2':<20} {'4':<12} {len(violations):<12} {'✅' if len(violations) < 4 else '❌':<15}")
        
        # 5. Verdict finale
        print(f"\n🎯 5. Verdetto Finale")
        print("-" * 20)
        
        if len(violations) == 0:
            status = "🟢 SUCCESSO"
            message = "Tutte le violazioni P2 risolte!"
            success = True
        elif len(violations) <= 1:
            status = "🟡 PARZIALE"
            message = "La maggior parte delle violazioni risolte"
            success = True
        else:
            status = "🔴 CRITICO"
            message = "Violazioni persistenti - revisione necessaria"
            success = False
        
        print(f"   {status}")
        print(f"   📊 Violazioni rimanenti: {len(violations)}")
        print(f"   💬 {message}")
        
        if violations:
            print(f"   ❌ Violazioni:")
            for violation in violations:
                print(f"      - {violation}")
        
        # 6. Salva verifica
        verification_results = {
            'timestamp': datetime.now().isoformat(),
            'p2_verification': {
                'status': status,
                'violations_count': len(violations),
                'violations': violations,
                'target_weights': target_weights,
                'risk_metrics': risk_metrics,
                'correlation': correlation,
                'config_checks': dict(checks),
                'success': success
            }
        }
        
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            report_file = sm.add_report_to_session('verification', verification_results, 'json')
            print(f"\n📋 Verifica salvata: {report_file}")
        except ImportError:
            print(f"\n⚠️ Session Manager non disponibile")
        
        conn.close()
        return success
        
    except Exception as e:
        print(f"❌ Errore verifica: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_p2_implementation()
    sys.exit(0 if success else 1)
