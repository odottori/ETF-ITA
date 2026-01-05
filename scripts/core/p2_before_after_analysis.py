#!/usr/bin/env python3
"""
P2 Before/After Analysis - ETF Italia Project v10
Confronto effetti delle correzioni rischio portafoglio
"""

import sys
import os
import json
import duckdb
import numpy as np
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def calculate_portfolio_metrics(weights, volatilities, correlation):
    """Calcola metriche portfolio dati pesi, vol e correlazione"""
    
    # Per 2 asset: portfolio variance = w1²σ1² + w2²σ2² + 2w1w2σ1σ2ρ
    w1, w2 = weights
    v1, v2 = volatilities
    
    portfolio_variance = (w1**2 * v1**2 + w2**2 * v2**2 + 2*w1*w2*v1*v2*correlation)
    portfolio_vol = np.sqrt(portfolio_variance)
    
    # Contribution to risk
    contrib1 = w1 * v1 * (w1*v1 + w2*v2*correlation) / portfolio_vol if portfolio_vol > 0 else 0
    contrib2 = w2 * v2 * (w2*v2 + w1*v1*correlation) / portfolio_vol if portfolio_vol > 0 else 0
    
    return {
        'portfolio_vol': portfolio_vol,
        'contribution_to_risk': { 'CSSPX.MI': contrib1, 'XS2L.MI': contrib2 },
        'diversification_ratio': portfolio_vol / (w1*v1 + w2*v2) if (w1*v1 + w2*v2) > 0 else 0
    }

def run_before_after_analysis():
    """Analisi comparativa prima/dopo correzioni"""
    
    print("🔍 P2 — Before/After Analysis: Effetti Correzioni Rischio")
    print("=" * 65)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # Dati correnti
        print("\n📊 DATI CORRENTI (Prima della Cura)")
        print("-" * 40)
        
        # Recupera dati reali
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
        
        correlation = correlation_data[0] if correlation_data else 0.8353
        
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
        
        # Scenario PRIMA (50/50)
        weights_before = {'CSSPX.MI': 0.5, 'XS2L.MI': 0.5}
        metrics_before = calculate_portfolio_metrics(
            [weights_before['CSSPX.MI'], weights_before['XS2L.MI']], 
            [volatilities['CSSPX.MI'], volatilities['XS2L.MI']], 
            correlation
        )
        
        print(f"   📈 Pesi: CSSPX {weights_before['CSSPX.MI']:.0%} | XS2L {weights_before['XS2L.MI']:.0%}")
        print(f"   🔗 Correlazione: {correlation:.3f}")
        print(f"   📊 Volatilità: CSSPX {volatilities['CSSPX.MI']:.1%} | XS2L {volatilities['XS2L.MI']:.1%}")
        print(f"   🎯 Portfolio Vol: {metrics_before['portfolio_vol']:.1%}")
        print(f"   ⚖️ Contribution-to-Risk:")
        for symbol, contrib in metrics_before['contribution_to_risk'].items():
            weight = weights_before[symbol]
            print(f"      {symbol}: {contrib:.1%} (peso {weight:.0%})")
        print(f"   🔄 Diversification Ratio: {metrics_before['diversification_ratio']:.3f}")
        
        # Violazioni correnti
        violations_before = []
        if correlation > 0.7:
            violations_before.append(f"Correlazione {correlation:.3f} > 0.7")
        
        max_contribution = max(metrics_before['contribution_to_risk'].values())
        if max_contribution > 0.6:
            max_symbol = max(metrics_before['contribution_to_risk'], key=metrics_before['contribution_to_risk'].get)
            violations_before.append(f"Concentrazione {max_symbol} {max_contribution:.1%} > 60%")
        
        if metrics_before['portfolio_vol'] > 0.20:
            violations_before.append(f"Portfolio vol {metrics_before['portfolio_vol']:.1%} > 20%")
        
        print(f"   🚨 Violazioni: {len(violations_before)}")
        for violation in violations_before:
            print(f"      ❌ {violation}")
        
        # Scenario DOPO le correzioni
        print("\n🔧 SCENARIO POST-CORREZIONI")
        print("-" * 35)
        
        # Opzione 1: Solo ribilanciamento pesi (40/60)
        weights_option1 = {'CSSPX.MI': 0.6, 'XS2L.MI': 0.4}
        metrics_option1 = calculate_portfolio_metrics(
            [weights_option1['CSSPX.MI'], weights_option1['XS2L.MI']], 
            [volatilities['CSSPX.MI'], volatilities['XS2L.MI']], 
            correlation
        )
        
        print(f"\n1️⃣ OPZIONE 1: Ribilanciamento Pesi (60/40)")
        print(f"   📈 Pesi: CSSPX {weights_option1['CSSPX.MI']:.0%} | XS2L {weights_option1['XS2L.MI']:.0%}")
        print(f"   🎯 Portfolio Vol: {metrics_option1['portfolio_vol']:.1%}")
        print(f"   ⚖️ Contribution-to-Risk:")
        for symbol, contrib in metrics_option1['contribution_to_risk'].items():
            weight = weights_option1[symbol]
            print(f"      {symbol}: {contrib:.1%} (peso {weight:.0%})")
        
        violations_opt1 = []
        max_contribution_opt1 = max(metrics_option1['contribution_to_risk'].values())
        if max_contribution_opt1 > 0.6:
            max_symbol_opt1 = max(metrics_option1['contribution_to_risk'], key=metrics_option1['contribution_to_risk'].get)
            violations_opt1.append(f"Concentrazione {max_symbol_opt1} {max_contribution_opt1:.1%} > 60%")
        
        print(f"   🚨 Violazioni: {len(violations_opt1)}")
        
        # Opzione 2: Aggiunta asset decorrelato (Bond)
        print(f"\n2️⃣ OPZIONE 2: Diversificazione con Bond (50/30/20)")
        
        # Simula bond ETF con correlazione bassa
        bond_vol = 0.08  # 8% volatilità bond
        bond_correlation_csspx = 0.2  # Bassa correlazione con azioni
        bond_correlation_xs2l = 0.15  # Ancora più bassa con leveraged
        
        weights_option2 = {'CSSPX.MI': 0.5, 'XS2L.MI': 0.3, 'BOND.MI': 0.2}
        
        # Calcolo portfolio variance per 3 asset
        w_csspx, w_xs2l, w_bond = weights_option2['CSSPX.MI'], weights_option2['XS2L.MI'], weights_option2['BOND.MI']
        v_csspx, v_xs2l, v_bond = volatilities['CSSPX.MI'], volatilities['XS2L.MI'], bond_vol
        
        # Portfolio variance 3 asset
        portfolio_var_opt2 = (
            w_csspx**2 * v_csspx**2 + 
            w_xs2l**2 * v_xs2l**2 + 
            w_bond**2 * v_bond**2 +
            2*w_csspx*w_xs2l*v_csspx*v_xs2l*correlation +
            2*w_csspx*w_bond*v_csspx*v_bond*bond_correlation_csspx +
            2*w_xs2l*w_bond*v_xs2l*v_bond*bond_correlation_xs2l
        )
        
        portfolio_vol_opt2 = np.sqrt(portfolio_var_opt2)
        
        # Contribution to risk per 3 asset
        contrib_csspx_opt2 = (w_csspx*v_csspx * (w_csspx*v_csspx + w_xs2l*v_xs2l*correlation + w_bond*v_bond*bond_correlation_csspx)) / portfolio_vol_opt2
        contrib_xs2l_opt2 = (w_xs2l*v_xs2l * (w_xs2l*v_xs2l + w_csspx*v_csspx*correlation + w_bond*v_bond*bond_correlation_xs2l)) / portfolio_vol_opt2
        contrib_bond_opt2 = (w_bond*v_bond * (w_bond*v_bond + w_csspx*v_csspx*bond_correlation_csspx + w_xs2l*v_xs2l*bond_correlation_xs2l)) / portfolio_vol_opt2
        
        contribution_to_risk_opt2 = {
            'CSSPX.MI': contrib_csspx_opt2,
            'XS2L.MI': contrib_xs2l_opt2,
            'BOND.MI': contrib_bond_opt2
        }
        
        print(f"   📈 Pesi: CSSPX {weights_option2['CSSPX.MI']:.0%} | XS2L {weights_option2['XS2L.MI']:.0%} | BOND {weights_option2['BOND.MI']:.0%}")
        print(f"   🎯 Portfolio Vol: {portfolio_vol_opt2:.1%}")
        print(f"   ⚖️ Contribution-to-Risk:")
        for symbol, contrib in contribution_to_risk_opt2.items():
            weight = weights_option2[symbol]
            print(f"      {symbol}: {contrib:.1%} (peso {weight:.0%})")
        
        violations_opt2 = []
        max_contribution_opt2 = max(contribution_to_risk_opt2.values())
        if max_contribution_opt2 > 0.6:
            max_symbol_opt2 = max(contribution_to_risk_opt2, key=contribution_to_risk_opt2.get)
            violations_opt2.append(f"Concentrazione {max_symbol_opt2} {max_contribution_opt2:.1%} > 60%")
        
        print(f"   🚨 Violazioni: {len(violations_opt2)}")
        
        # Opzione 3: Vol targeting aggressivo
        print(f"\n3️⃣ OPZIONE 3: Vol Targeting Aggressivo")
        
        # Target volatilità 15%
        target_vol = 0.15
        current_vol = metrics_before['portfolio_vol']
        scaling_factor = target_vol / current_vol if current_vol > 0 else 1.0
        
        weights_option3 = {
            'CSSPX.MI': weights_before['CSSPX.MI'] * scaling_factor,
            'XS2L.MI': weights_before['XS2L.MI'] * scaling_factor
        }
        
        # Il resto va in cash
        cash_allocation = 1.0 - sum(weights_option3.values())
        
        metrics_option3 = calculate_portfolio_metrics(
            [weights_option3['CSSPX.MI'], weights_option3['XS2L.MI']], 
            [volatilities['CSSPX.MI'], volatilities['XS2L.MI']], 
            correlation
        )
        
        print(f"   📈 Pesi: CSSPX {weights_option3['CSSPX.MI']:.0%} | XS2L {weights_option3['XS2L.MI']:.0%} | CASH {cash_allocation:.0%}")
        print(f"   🎯 Portfolio Vol: {metrics_option3['portfolio_vol']:.1%} (target {target_vol:.0%})")
        print(f"   ⚖️ Contribution-to-Risk:")
        for symbol, contrib in metrics_option3['contribution_to_risk'].items():
            weight = weights_option3[symbol]
            print(f"      {symbol}: {contrib:.1%} (peso {weight:.0%})")
        
        violations_opt3 = []
        max_contribution_opt3 = max(metrics_option3['contribution_to_risk'].values())
        if max_contribution_opt3 > 0.6:
            max_symbol_opt3 = max(metrics_option3['contribution_to_risk'], key=metrics_option3['contribution_to_risk'].get)
            violations_opt3.append(f"Concentrazione {max_symbol_opt3} {max_contribution_opt3:.1%} > 60%")
        
        print(f"   🚨 Violazioni: {len(violations_opt3)}")
        
        # Tabella comparativa
        print(f"\n📋 TABELLA COMPARATIVA")
        print("-" * 50)
        print(f"{'Scenario':<20} {'Vol':<8} {'Max Conc':<10} {'Violazioni':<12} {'Cash':<8}")
        print("-" * 50)
        print(f"{'Prima (50/50)':<20} {metrics_before['portfolio_vol']:<8.1%} {max_contribution:<10.1%} {len(violations_before):<12} {'0%':<8}")
        print(f"{'Opz1 (60/40)':<20} {metrics_option1['portfolio_vol']:<8.1%} {max_contribution_opt1:<10.1%} {len(violations_opt1):<12} {'0%':<8}")
        print(f"{'Opz2 (+Bond)':<20} {portfolio_vol_opt2:<8.1%} {max_contribution_opt2:<10.1%} {len(violations_opt2):<12} {'0%':<8}")
        print(f"{'Opz3 (Vol Target)':<20} {metrics_option3['portfolio_vol']:<8.1%} {max_contribution_opt3:<10.1%} {len(violations_opt3):<12} {cash_allocation:<8.1%}")
        
        # Analisi benefici
        print(f"\n💡 ANALISI BENEFICI")
        print("-" * 25)
        
        vol_reduction_opt1 = (metrics_before['portfolio_vol'] - metrics_option1['portfolio_vol']) / metrics_before['portfolio_vol']
        vol_reduction_opt2 = (metrics_before['portfolio_vol'] - portfolio_vol_opt2) / metrics_before['portfolio_vol']
        vol_reduction_opt3 = (metrics_before['portfolio_vol'] - metrics_option3['portfolio_vol']) / metrics_before['portfolio_vol']
        
        print(f"📉 Riduzione Volatilità:")
        print(f"   Opz1 (60/40): {vol_reduction_opt1:+.1%}")
        print(f"   Opz2 (+Bond): {vol_reduction_opt2:+.1%}")
        print(f"   Opz3 (Vol Target): {vol_reduction_opt3:+.1%}")
        
        print(f"\n⚖️ Miglioramento Diversificazione:")
        print(f"   Opz1: Concentrazione max {max_contribution_opt1:.1%} → {max_contribution:.1%}")
        print(f"   Opz2: Concentrazione max {max_contribution_opt2:.1%} → {max_contribution:.1%}")
        print(f"   Opz3: Concentrazione max {max_contribution_opt3:.1%} → {max_contribution:.1%}")
        
        # Raccomandazione finale
        print(f"\n🎯 RACCOMANDAZIONE FINALE")
        print("-" * 25)
        
        if len(violations_opt2) == 0:
            best_option = "Opzione 2 (+Bond)"
            reason = "Elimina tutte le violazioni con migliore diversificazione"
        elif len(violations_opt1) <= len(violations_opt3):
            best_option = "Opzione 1 (60/40)"
            reason = "Semplice implementazione, riduce significativamente le violazioni"
        else:
            best_option = "Opzione 3 (Vol Target)"
            reason = "Controllo preciso volatilità con cash buffer"
        
        print(f"🏆 Miglior opzione: {best_option}")
        print(f"📝 Motivazione: {reason}")
        
        # Salva analisi
        results = {
            'timestamp': datetime.now().isoformat(),
            'before_after_analysis': {
                'before': {
                    'weights': weights_before,
                    'correlation': correlation,
                    'volatilities': volatilities,
                    'portfolio_vol': metrics_before['portfolio_vol'],
                    'contribution_to_risk': metrics_before['contribution_to_risk'],
                    'violations': violations_before
                },
                'option1': {
                    'description': 'Ribilanciamento 60/40',
                    'weights': weights_option1,
                    'portfolio_vol': metrics_option1['portfolio_vol'],
                    'contribution_to_risk': metrics_option1['contribution_to_risk'],
                    'violations': violations_opt1,
                    'vol_reduction': vol_reduction_opt1
                },
                'option2': {
                    'description': 'Diversificazione +Bond 50/30/20',
                    'weights': weights_option2,
                    'portfolio_vol': portfolio_vol_opt2,
                    'contribution_to_risk': contribution_to_risk_opt2,
                    'violations': violations_opt2,
                    'vol_reduction': vol_reduction_opt2
                },
                'option3': {
                    'description': 'Vol Targeting con Cash',
                    'weights': weights_option3,
                    'cash_allocation': cash_allocation,
                    'portfolio_vol': metrics_option3['portfolio_vol'],
                    'contribution_to_risk': metrics_option3['contribution_to_risk'],
                    'violations': violations_opt3,
                    'vol_reduction': vol_reduction_opt3
                },
                'recommendation': {
                    'best_option': best_option,
                    'reason': reason
                }
            }
        }
        
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            report_file = sm.add_report_to_session('analysis', results, 'json')
            print(f"\n📋 Analisi completa salvata: {report_file}")
        except ImportError:
            print(f"\n⚠️ Session Manager non disponibile")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = run_before_after_analysis()
    sys.exit(0 if success else 1)
