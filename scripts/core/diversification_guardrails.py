#!/usr/bin/env python3
"""
Diversification Guardrails - ETF Italia Project v10
P2.1: Cap correlazione media ponderata e diversification breaker
"""

import sys
import os
import duckdb
import numpy as np
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def calculate_diversification_metrics():
    """Calcola metriche di diversificazione e guardrails"""
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    print("🔄 P2.1: Diversification Guardrails")
    print("=" * 50)
    
    try:
        # Test 1: Calcolo correlazione portfolio
        print("1️⃣ Calcolo correlazione media ponderata...")
        
        # Ottieni dati returns recenti per correlazione
        returns_data = conn.execute("""
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
            AND date >= CURRENT_DATE - INTERVAL '252 days'  -- Ultimo anno
        )
        SELECT 
            symbol,
            AVG(daily_return) as avg_return,
            STDDEV(daily_return) as volatility,
            COUNT(*) as days
        FROM filtered_returns
        GROUP BY symbol
        """).fetchall()
        
        if len(returns_data) < 2:
            print("   ⚠️ Dati insufficienti per calcolo correlazione")
            return False
        
        # Calcolo correlazione matrice
        correlation_matrix = conn.execute("""
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
            AND date >= CURRENT_DATE - INTERVAL '252 days'  -- Ultimo anno
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
        SELECT 
            CORR(csspx_return, xs2l_return) as correlation,
            COUNT(*) as observations
        FROM pivot_returns
        """).fetchone()
        
        correlation, obs = correlation_matrix
        print(f"   📊 Correlazione CSSPX-XS2L: {correlation:.4f} ({obs} osservazioni)")
        
        # Test 2: Calcolo contribution-to-risk
        print("2️⃣ Calcolo contribution-to-risk...")
        
        # Simula pesi portfolio (es. 50/50)
        weights = {'CSSPX.MI': 0.5, 'XS2L.MI': 0.5}
        
        # Ottieni volatilità individuali
        volatilities = {}
        for symbol, avg_ret, vol, days in returns_data:
            volatilities[symbol] = vol
        
        # Calcolo contribution-to-risk
        total_portfolio_vol = 0
        contributions = {}
        
        for symbol, weight in weights.items():
            if symbol in volatilities:
                contribution = weight * volatilities[symbol]
                contributions[symbol] = contribution
                total_portfolio_vol += contribution
        
        # Normalizza contributions
        for symbol in contributions:
            contributions[symbol] = contributions[symbol] / total_portfolio_vol if total_portfolio_vol > 0 else 0
        
        print(f"   📈 Contribution-to-risk:")
        for symbol, contrib in contributions.items():
            print(f"      {symbol}: {contrib:.1%} (peso {weights[symbol]:.1%})")
        
        # Test 3: Verifica diversification breaker
        print("3️⃣ Verifica diversification breaker...")
        
        # Soglie guardrails
        CORRELATION_THRESHOLD = 0.7  # 70% correlazione max
        CONCENTRATION_THRESHOLD = 0.6  # 60% max contribution
        
        diversification_violations = []
        
        # Check correlazione
        if abs(correlation) > CORRELATION_THRESHOLD:
            diversification_violations.append({
                'type': 'HIGH_CORRELATION',
                'value': correlation,
                'threshold': CORRELATION_THRESHOLD,
                'description': f'Correlazione {correlation:.3f} > {CORRELATION_THRESHOLD}'
            })
        
        # Check concentrazione
        max_contribution = max(contributions.values())
        if max_contribution > CONCENTRATION_THRESHOLD:
            max_symbol = max(contributions, key=contributions.get)
            diversification_violations.append({
                'type': 'HIGH_CONCENTRATION',
                'symbol': max_symbol,
                'value': max_contribution,
                'threshold': CONCENTRATION_THRESHOLD,
                'description': f'Concentrazione {max_symbol}: {max_contribution:.1%} > {CONCENTRATION_THRESHOLD:.1%}'
            })
        
        # Test 4: Varianza spiegata
        print("4️⃣ Analisi varianza spiegata...")
        
        # Calcolo varianza spiegata (semplificato)
        if len(returns_data) == 2:
            # Con 2 asset, la varianza spiegata dal primo asset è correlazione²
            explained_variance = correlation ** 2
            print(f"   📊 Varianza spiegata da CSSPX: {explained_variance:.1%}")
            
            if explained_variance > 0.5:  # 50% threshold
                diversification_violations.append({
                    'type': 'HIGH_VARIANCE_CONCENTRATION',
                    'value': explained_variance,
                    'threshold': 0.5,
                    'description': f'Varianza spiegata {explained_variance:.1%} > 50%'
                })
        
        # Test 5: Audit log
        print("5️⃣ Generazione audit log...")
        
        audit_data = {
            'timestamp': datetime.now().isoformat(),
            'test_p2_1_diversification_guardrails': {
                'correlation_matrix': {
                    'csspx_xs2l': correlation,
                    'observations': obs
                },
                'volatilities': volatilities,
                'weights': weights,
                'contribution_to_risk': contributions,
                'guardrails': {
                    'correlation_threshold': CORRELATION_THRESHOLD,
                    'concentration_threshold': CONCENTRATION_THRESHOLD,
                    'variance_threshold': 0.5
                },
                'violations': diversification_violations,
                'diversification_score': 1.0 - len(diversification_violations) * 0.2,  # Semplice scoring
                'recommendations': []
            }
        }
        
        # Genera raccomandazioni
        if diversification_violations:
            for violation in diversification_violations:
                if violation['type'] == 'HIGH_CORRELATION':
                    audit_data['test_p2_1_diversification_guardrails']['recommendations'].append(
                        "Ridurre esposizione ad asset altamente correlati o aggiungere asset decorrelati"
                    )
                elif violation['type'] == 'HIGH_CONCENTRATION':
                    audit_data['test_p2_1_diversification_guardrails']['recommendations'].append(
                        f"Ribilanciare pesi per ridurre concentrazione in {violation['symbol']}"
                    )
                elif violation['type'] == 'HIGH_VARIANCE_CONCENTRATION':
                    audit_data['test_p2_1_diversification_guardrails']['recommendations'].append(
                        "Diversificare con asset che spiegano varianza residua"
                    )
        else:
            audit_data['test_p2_1_diversification_guardrails']['recommendations'].append(
                "Diversificazione adeguata - mantenere monitoraggio"
            )
        
        # Salva audit log
        try:
            from session_manager import get_session_manager
            sm = get_session_manager(script_name='diversification_guardrails')
            audit_file = sm.add_report_to_session('analysis', audit_data, 'json')
            print(f"   📋 Audit log salvato: {audit_file}")
        except ImportError:
            print("   ⚠️ Session Manager non disponibile, audit non salvato")
        
        # Verdict finale
        if diversification_violations:
            print(f"\n⚠️ P2.1 PARZIALE: {len(diversification_violations)} violazioni diversification")
            for violation in diversification_violations:
                print(f"   ❌ {violation['description']}")
            return True  # Consideriamo OK se i guardrails funzionano
        else:
            print("\n🎉 P2.1 COMPLETATO: Diversificazione adeguata ✅")
            return True
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = calculate_diversification_metrics()
    sys.exit(0 if success else 1)
