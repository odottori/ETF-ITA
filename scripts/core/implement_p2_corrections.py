#!/usr/bin/env python3
"""
P2 Implementation Script - ETF Italia Project v10
Implementazione correzioni rischio portafoglio P2
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def implement_p2_corrections():
    """Implementa le correzioni P2 nel sistema"""
    
    print("🔧 P2 — IMPLEMENTAZIONE CORREZIONI RISCHIO PORTAFOGLIO")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    
    try:
        # 1. Backup configurazione attuale
        print("\n📋 1. Backup Configurazione Attuale")
        print("-" * 35)
        
        with open(config_path, 'r') as f:
            current_config = json.load(f)
        
        backup_path = config_path.replace('.json', '_backup_p2.json')
        with open(backup_path, 'w') as f:
            json.dump(current_config, f, indent=2)
        
        print(f"   ✅ Backup salvato: {backup_path}")
        
        # 2. Aggiornamento configurazione con correzioni P2
        print("\n🔧 2. Aggiornamento Configurazione P2")
        print("-" * 35)
        
        # Aggiungi bond ETF all'universo
        bond_etf = {
            "symbol": "AGGH.MI",
            "name": "iShares Core Global Aggregate Bond EUR Hedged",
            "dist_policy": "ACC",
            "ter": 0.10,
            "currency": "EUR",
            "tax_category": "OICR_ETF",
            "aum_eur": 1000000000,
            "cost_model": {
                "commission_pct": 0.001,
                "slippage_bps": 3
            },
            "execution_model": "T+1_OPEN",
            "fx_enabled": false
        }
        
        current_config['universe']['bond'] = [bond_etf]
        
        # Aggiorna risk management con guardrails P2
        current_config['risk_management'].update({
            'correlation_threshold': 0.7,
            'concentration_threshold': 0.5,
            'diversification_breaker_threshold': 0.5,
            'xs2l_position_cap': 0.35,
            'bond_allocation_min': 0.15,
            'volatility_target_optimized': 0.20,
            'p2_guardrails_enabled': True
        })
        
        # Salva nuova configurazione
        with open(config_path, 'w') as f:
            json.dump(current_config, f, indent=2)
        
        print("   ✅ Configurazione aggiornata:")
        print("      - Aggiunto AGGH.MI (Bond ETF)")
        print("      - Guardrails P2 abilitati")
        print("      - Thresholds correlazione/concentrazione")
        print("      - Position cap XS2L 35%")
        
        # 3. Verifica database
        print("\n🔍 3. Verifica Database")
        print("-" * 25)
        
        conn = duckdb.connect(db_path)
        
        # Controlla se esistono già dati per AGGH
        check_aggh = conn.execute("""
        SELECT COUNT(*) FROM market_data WHERE symbol = 'AGGH.MI'
        """).fetchone()[0]
        
        print(f"   📊 Dati AGGH.MI esistenti: {check_aggh} records")
        
        # 4. Simulazione nuovo portafoglio
        print("\n📈 4. Simulazione Nuovo Portfolio")
        print("-" * 35)
        
        # Pesi target post-correzione
        target_weights = {
            'CSSPX.MI': 0.50,
            'XS2L.MI': 0.30,
            'AGGH.MI': 0.20
        }
        
        print("   🎯 Pesi target:")
        for symbol, weight in target_weights.items():
            print(f"      {symbol}: {weight:.0%}")
        
        # Calcola metriche simulate
        vol_data = conn.execute("""
        WITH daily_returns AS (
            SELECT 
                symbol,
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
        
        # Simula volatilità bond (8% annuo)
        volatilities['AGGH.MI'] = 0.08
        
        # Calcola portfolio vol (simplified)
        portfolio_vol = (
            target_weights['CSSPX.MI'] * volatilities['CSSPX.MI'] +
            target_weights['XS2L.MI'] * volatilities['XS2L.MI'] +
            target_weights['AGGH.MI'] * volatilities['AGGH.MI']
        )
        
        print(f"   📊 Volatilità stimata: {portfolio_vol:.1%}")
        
        # 5. Genera ordini proposti
        print("\n📋 5. Ordini Proposti")
        print("-" * 25)
        
        orders = []
        
        # Ordine 1: Acquisto AGGH.MI
        orders.append({
            'symbol': 'AGGH.MI',
            'action': 'BUY',
            'target_weight': 0.20,
            'current_weight': 0.00,
            'reason': 'P2 diversification - aggiunta bond per ridurre correlazione',
            'priority': 'HIGH',
            'implementation': 'gradual_2_weeks'
        })
        
        # Ordine 2: Riduzione XS2L.MI
        orders.append({
            'symbol': 'XS2L.MI',
            'action': 'SELL',
            'target_weight': 0.30,
            'current_weight': 0.50,
            'reason': 'P2 concentration reduction - da 50% a 30%',
            'priority': 'HIGH',
            'implementation': 'gradual_1_week'
        })
        
        # Ordine 3: Aumento CSSPX.MI
        orders.append({
            'symbol': 'CSSPX.MI',
            'action': 'BUY',
            'target_weight': 0.50,
            'current_weight': 0.50,
            'reason': 'P2 rebalancing - mantenimento peso',
            'priority': 'MEDIUM',
            'implementation': 'gradual_2_weeks'
        })
        
        for i, order in enumerate(orders, 1):
            print(f"   {i}. {order['action']} {order['symbol']}")
            print(f"      Peso: {order['current_weight']:.0%} → {order['target_weight']:.0%}")
            print(f"      Motivo: {order['reason']}")
            print(f"      Priorità: {order['priority']}")
        
        # 6. Salva piano implementazione
        print("\n💾 6. Salvataggio Piano Implementazione")
        print("-" * 40)
        
        implementation_plan = {
            'timestamp': datetime.now().isoformat(),
            'p2_implementation': {
                'status': 'READY',
                'backup_config': backup_path,
                'target_weights': target_weights,
                'orders': orders,
                'expected_metrics': {
                    'portfolio_volatility': portfolio_vol,
                    'correlation_reduction': 'target < 70%',
                    'concentration_reduction': 'target < 50%',
                    'violations_resolved': 4
                },
                'timeline': {
                    'week_1': 'Start XS2L reduction (50%→40%)',
                    'week_2': 'Complete XS2L reduction, start AGGH accumulation',
                    'week_3_4': 'Complete AGGH to 20%, CSSPX rebalancing',
                    'week_5': 'Final adjustments and monitoring'
                }
            }
        }
        
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            plan_file = sm.add_report_to_session('implementation', implementation_plan, 'json')
            print(f"   ✅ Piano salvato: {plan_file}")
        except ImportError:
            print("   ⚠️ Session Manager non disponibile")
        
        # 7. Verifica finale
        print("\n✅ 7. Verifica Finale")
        print("-" * 20)
        
        # Verifica configurazione
        with open(config_path, 'r') as f:
            updated_config = json.load(f)
        
        checks = [
            ('Bond ETF aggiunto', 'bond' in updated_config['universe']),
            ('Guardrails P2 abilitati', updated_config['risk_management'].get('p2_guardrails_enabled', False)),
            ('Threshold correlazione', updated_config['risk_management'].get('correlation_threshold', 0) > 0),
            ('Position cap XS2L', updated_config['risk_management'].get('xs2l_position_cap', 0) > 0)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print(f"\n🎉 P2 IMPLEMENTAZIONE COMPLETATA CON SUCCESSO!")
            print(f"   📋 Configurazione aggiornata")
            print(f"   📊 Piano ordini generato")
            print(f"   🛡️ Guardrails P2 abilitati")
            print(f"\n🚀 PROSSIMO PASSO: Eseguire ordini secondo timeline")
        else:
            print(f"\n⚠️ IMPLEMENTAZIONE PARZIALE - Verificare errori")
        
        conn.close()
        return all_passed
        
    except Exception as e:
        print(f"❌ Errore implementazione: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = implement_p2_corrections()
    sys.exit(0 if success else 1)
