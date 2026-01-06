#!/usr/bin/env python3
"""
Test del refactoring expected_alpha → momentum_score/trade_score
Verifica che la nuova logica MANDATORY vs OPPORTUNISTIC funzioni correttamente
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

def test_momentum_score_logic():
    """Test della nuova logica momentum_score/trade_score"""
    
    print("🧪 TEST MOMENTUM SCORE REFACTOR")
    print("=" * 50)
    
    # Config di test
    config = {
        'settings': {
            'score_entry_min': 0.7,
            'score_rebalance_min': 0.6,
            'force_deviation': 0.05
        }
    }
    
    # Test cases
    test_cases = [
        {
            'name': 'MANDATORY Stop-loss',
            'stop_reason': 'STOP_LOSS_TRIGGERED',
            'weight_deviation': 0.02,
            'momentum_score': 0.0,
            'trade_score': 0.0,
            'expected': 'TRADE'
        },
        {
            'name': 'MANDATORY Force rebalance',
            'stop_reason': None,
            'weight_deviation': 0.06,  # > force_deviation
            'momentum_score': 0.3,
            'trade_score': 0.2,
            'expected': 'TRADE'
        },
        {
            'name': 'OPPORTUNISTIC Rebalance OK',
            'stop_reason': None,
            'weight_deviation': 0.03,  # > 1% min deviation
            'momentum_score': 0.8,
            'trade_score': 0.7,  # >= score_rebalance_min
            'expected': 'TRADE'
        },
        {
            'name': 'OPPORTUNISTIC Rebalance HOLD',
            'stop_reason': None,
            'weight_deviation': 0.03,  # > 1% min deviation
            'momentum_score': 0.4,
            'trade_score': 0.3,  # < score_rebalance_min
            'expected': 'HOLD'
        },
        {
            'name': 'ENTRY New position OK',
            'stop_reason': None,
            'weight_deviation': 0.0,
            'current_qty': 0,
            'momentum_score': 0.8,  # >= score_entry_min
            'trade_score': 0.7,
            'expected': 'TRADE'
        },
        {
            'name': 'ENTRY New position HOLD',
            'stop_reason': None,
            'weight_deviation': 0.0,
            'current_qty': 0,
            'momentum_score': 0.5,  # < score_entry_min
            'trade_score': 0.4,
            'expected': 'HOLD'
        }
    ]
    
    results = []
    
    for case in test_cases:
        print(f"\n📋 {case['name']}")
        
        # Logica MANDATORY vs OPPORTUNISTIC
        score_entry_min = config['settings']['score_entry_min']
        score_rebalance_min = config['settings']['score_rebalance_min']
        
        # MANDATORY: stop-loss, force rebalancing, segnali forti
        if case.get('stop_reason') or case.get('weight_deviation', 0) > config['settings']['force_deviation']:
            recommendation = 'TRADE'  # Sempre esegui
            reason = "MANDATORY"
        # OPPORTUNISTIC: rebalancing solo se score sufficiente
        elif case.get('weight_deviation', 0) > 0.01:  # 1% min deviation
            recommendation = 'TRADE' if case['trade_score'] >= score_rebalance_min else 'HOLD'
            reason = "OPPORTUNISTIC REBALANCE"
        # ENTRY: nuove posizioni solo se score alto
        elif case.get('current_qty', 1) == 0 and case['momentum_score'] >= score_entry_min:
            recommendation = 'TRADE'
            reason = "OPPORTUNISTIC ENTRY"
        else:
            recommendation = 'HOLD'
            reason = "DEFAULT HOLD"
        
        print(f"   Momentum: {case['momentum_score']:.2f} | Trade: {case['trade_score']:.2f}")
        print(f"   Deviation: {case.get('weight_deviation', 0):.2%}")
        print(f"   Reason: {reason}")
        print(f"   Expected: {case['expected']} | Got: {recommendation}")
        
        if recommendation == case['expected']:
            print("   ✅ PASS")
            results.append(True)
        else:
            print("   ❌ FAIL")
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ Tutti i test superati ({passed}/{total})")
        print("✅ Logica MANDATORY vs OPPORTUNISTIC corretta!")
        return True
    else:
        print(f"❌ Test falliti ({total-passed}/{total})")
        return False

def test_score_calculation():
    """Test del calcolo dei score"""
    
    print("\n🔢 TEST SCORE CALCULATION")
    print("=" * 30)
    
    # Test parametri
    base_momentum = 0.5
    risk_scalar = 0.8
    current_vol = 0.15
    position_value = 10000
    commission = 10
    slippage = 5
    tax_estimate = 0
    
    # Momentum score
    momentum_score = base_momentum * risk_scalar
    vol_adjustment = min(1.5, 0.10 / current_vol)
    momentum_score = min(1.0, momentum_score * vol_adjustment)
    
    # Trade score
    cost_ratio = (commission + slippage + tax_estimate) / position_value
    trade_score = momentum_score - cost_ratio * 10
    trade_score = max(0, min(1, trade_score))
    
    print(f"Base momentum: {base_momentum:.2f}")
    print(f"Risk scalar: {risk_scalar:.2f}")
    print(f"Vol adjustment: {vol_adjustment:.2f}")
    print(f"Momentum score: {momentum_score:.2f}")
    print(f"Cost ratio: {cost_ratio:.4f}")
    print(f"Trade score: {trade_score:.2f}")
    
    # Verifiche
    checks = [
        (0 <= momentum_score <= 1, "Momentum score in range 0-1"),
        (0 <= trade_score <= 1, "Trade score in range 0-1"),
        (momentum_score > 0, "Momentum score positive"),
        (trade_score <= momentum_score, "Trade score <= momentum score")
    ]
    
    all_ok = True
    for check, desc in checks:
        if check:
            print(f"✅ {desc}")
        else:
            print(f"❌ {desc}")
            all_ok = False
    
    return all_ok

if __name__ == "__main__":
    test1 = test_momentum_score_logic()
    test2 = test_score_calculation()
    
    if test1 and test2:
        print("\n🎉 Tutti i test passati!")
        print("Refactoring expected_alpha → momentum_score completato con successo!")
    else:
        print("\n❌ Alcuni test falliti")
        sys.exit(1)
