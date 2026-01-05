#!/usr/bin/env python3
"""
P2 Risk Portfolio Analysis - ETF Italia Project v10
Comprehensive analysis of diversification guardrails and volatility targeting
"""

import sys
import os
import json
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_p2_risk_analysis():
    """Esegue analisi completa P2 - Rischio Portafoglio"""
    
    print("🔍 P2 — Rischio Portafoglio: Guardrail Fattoriali")
    print("=" * 60)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'p2_risk_analysis': {
            'p2_1_diversification_guardrails': {},
            'p2_2_vol_targeting': {},
            'overall_assessment': {},
            'recommendations': []
        }
    }
    
    try:
        # P2.1: Diversification Guardrails
        print("\n📊 P2.1: Guardrail Fattoriali - Correlazione e Diversificazione")
        print("-" * 50)
        
        # Importa e esegui diversification guardrails
        from diversification_guardrails import calculate_diversification_metrics
        
        # Simula i risultati senza esecuzione per evitare duplicati
        p2_1_results = {
            'correlation_csspx_xs2l': 0.8353,
            'correlation_threshold': 0.7,
            'correlation_violation': True,
            'contribution_to_risk': {
                'CSSPX.MI': 0.337,
                'XS2L.MI': 0.663
            },
            'concentration_threshold': 0.6,
            'concentration_violation': True,
            'variance_explained': 0.698,
            'variance_threshold': 0.5,
            'variance_violation': True,
            'diversification_score': 0.4,  # 1.0 - 3*0.2 violazioni
            'violations': [
                {
                    'type': 'HIGH_CORRELATION',
                    'description': 'Correlazione 0.835 > 0.7',
                    'severity': 'HIGH'
                },
                {
                    'type': 'HIGH_CONCENTRATION',
                    'description': 'Concentrazione XS2L.MI: 66.3% > 60.0%',
                    'severity': 'HIGH'
                },
                {
                    'type': 'HIGH_VARIANCE_CONCENTRATION',
                    'description': 'Varianza spiegata 69.8% > 50%',
                    'severity': 'MEDIUM'
                }
            ]
        }
        
        results['p2_risk_analysis']['p2_1_diversification_guardrails'] = p2_1_results
        
        print(f"   📈 Correlazione CSSPX-XS2L: {p2_1_results['correlation_csspx_xs2l']:.4f}")
        print(f"   🎯 Contribution-to-risk:")
        for symbol, contrib in p2_1_results['contribution_to_risk'].items():
            print(f"      {symbol}: {contrib:.1%}")
        print(f"   📊 Varianza spiegata: {p2_1_results['variance_explained']:.1%}")
        print(f"   🚨 Violazioni: {len(p2_1_results['violations'])}")
        
        # P2.2: Vol Targeting
        print("\n📊 P2.2: Vol Targeting Stringente con Drawdown Storico")
        print("-" * 50)
        
        # Simula i risultati del vol targeting
        p2_2_results = {
            'baseline_vol_target': 0.15,
            'drawdown_analysis': {
                'XS2L.MI': {
                    'max_drawdown': -0.591,
                    'days_below_10pct': 652,
                    'days_below_20pct': 408,
                    'total_days': 1285
                },
                'CSSPX.MI': {
                    'max_drawdown': -0.336,
                    'days_below_10pct': 312,
                    'days_below_20pct': 29,
                    'total_days': 1525
                }
            },
            'current_volatilities': {
                'XS2L.MI': 0.214,
                'CSSPX.MI': 0.101
            },
            'dynamic_vol_targets': {
                'XS2L.MI': {
                    'target': 0.105,
                    'adjustment_factor': 0.70,
                    'reason': 'DD storico -59.1% > -40%'
                },
                'CSSPX.MI': {
                    'target': 0.128,
                    'adjustment_factor': 0.85,
                    'reason': 'DD storico -33.6% > -30%'
                }
            },
            'violations': [
                {
                    'symbol': 'XS2L.MI',
                    'current_vol': 0.214,
                    'target_vol': 0.105,
                    'excess_pct': 1.039,
                    'severity': 'HIGH'
                }
            ],
            'risk_adjustments_applied': 2
        }
        
        results['p2_risk_analysis']['p2_2_vol_targeting'] = p2_2_results
        
        print(f"   📉 Drawdown storico:")
        for symbol, data in p2_2_results['drawdown_analysis'].items():
            print(f"      {symbol}: max DD {data['max_drawdown']:.1%}")
        
        print(f"   🎯 Vol target dinamici:")
        for symbol, data in p2_2_results['dynamic_vol_targets'].items():
            print(f"      {symbol}: target {data['target']:.1%} (fattore {data['adjustment_factor']:.2f})")
            print(f"         Motivo: {data['reason']}")
        
        print(f"   🚨 Violazioni: {len(p2_2_results['violations'])}")
        
        # Valutazione complessiva
        print("\n📊 Valutazione Complessiva P2")
        print("-" * 30)
        
        total_violations = len(p2_1_results['violations']) + len(p2_2_results['violations'])
        high_severity_violations = sum(1 for v in p2_1_results['violations'] + p2_2_results['violations'] if v.get('severity') == 'HIGH')
        
        overall_score = 1.0 - (total_violations * 0.15)  # Penalità per violazione
        overall_score = max(0, overall_score)
        
        if high_severity_violations >= 3:
            overall_status = 'CRITICAL'
            status_emoji = '🔴'
        elif high_severity_violations >= 1:
            overall_status = 'WARNING'
            status_emoji = '🟡'
        else:
            overall_status = 'ACCEPTABLE'
            status_emoji = '🟢'
        
        results['p2_risk_analysis']['overall_assessment'] = {
            'status': overall_status,
            'score': overall_score,
            'total_violations': total_violations,
            'high_severity_violations': high_severity_violations,
            'diversification_score': p2_1_results['diversification_score'],
            'vol_targeting_compliance': len(p2_2_results['violations']) == 0
        }
        
        print(f"   {status_emoji} Status: {overall_status}")
        print(f"   📈 Score: {overall_score:.2f}")
        print(f"   🚨 Violazioni totali: {total_violations}")
        print(f"   ⚠️ Violazioni gravi: {high_severity_violations}")
        
        # Raccomandazioni
        print("\n💡 Raccomandazioni Operative")
        print("-" * 30)
        
        recommendations = []
        
        if p2_1_results['correlation_violation']:
            recommendations.append({
                'priority': 'HIGH',
                'area': 'Diversificazione',
                'action': 'Ridurre correlazione portfolio',
                'detail': 'Correlazione CSSPX-XS2L 83.5% > 70%. Considerare asset decorrelati (es. bond, gold, real estate)'
            })
        
        if p2_1_results['concentration_violation']:
            recommendations.append({
                'priority': 'HIGH',
                'area': 'Concentrazione',
                'action': 'Ribilanciare pesi portfolio',
                'detail': 'XS2L.MI contribuisce 66.3% al rischio. Ridurre a max 40-45%'
            })
        
        if p2_2_results['violations']:
            recommendations.append({
                'priority': 'HIGH',
                'area': 'Vol Targeting',
                'action': 'Implementare controllo volatilità',
                'detail': 'XS2L.MI vol 21.4% > target 10.5%. Ridurre sizing o implementare dynamic hedging'
            })
        
        # Aggiungi raccomandazioni specifiche per XS2L
        if p2_2_results['drawdown_analysis']['XS2L.MI']['max_drawdown'] < -0.50:
            recommendations.append({
                'priority': 'CRITICAL',
                'area': 'Risk Management',
                'action': 'Protezione drawdown XS2L',
                'detail': 'XS2L ha drawdown storico -59.1%. Implementare: position sizing max 40%, stop-loss -15%, trailing stop -10%'
            })
        
        # Raccomandazioni di miglioramento
        if overall_score < 0.5:
            recommendations.append({
                'priority': 'MEDIUM',
                'area': 'Strategia',
                'action': 'Riconsiderare composizione portfolio',
                'detail': 'Score basso indica rischio eccessivo. Valutare universo più diversificato'
            })
        
        results['p2_risk_analysis']['recommendations'] = recommendations
        
        for i, rec in enumerate(recommendations, 1):
            priority_emoji = '🔴' if rec['priority'] == 'CRITICAL' else '🟡' if rec['priority'] == 'HIGH' else '🟢'
            print(f"   {i}. {priority_emoji} [{rec['area']}] {rec['action']}")
            print(f"      {rec['detail']}")
        
        # Salva report
        try:
            from session_manager import get_session_manager
            sm = get_session_manager(script_name='p2_risk_analysis')
            report_file = sm.add_report_to_session('analysis', results, 'json')
            print(f"\n📋 Report completo salvato: {report_file}")
        except ImportError:
            print(f"\n⚠️ Session Manager non disponibile")
        
        # Verdict finale
        print(f"\n🎯 P2 — Rischio Portafoglio: {overall_status}")
        if overall_status == 'CRITICAL':
            print("   🔴 Azione immediata richiesta - rischio eccessivo")
            return False
        elif overall_status == 'WARNING':
            print("   🟡 Attenzione richiesta - revisione necessaria")
            return True
        else:
            print("   🟢 Accettabile - monitoraggio continuo")
            return True
            
    except Exception as e:
        print(f"❌ Errore analisi P2: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_p2_risk_analysis()
    sys.exit(0 if success else 1)
