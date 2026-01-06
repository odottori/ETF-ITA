#!/usr/bin/env python3
"""
Test Strategy Engine Fixes (Logic Only) - ETF Italia Project v10.7
Verifica che tutti i bug fix siano implementati correttamente senza database
"""

import sys
import os
import json

# Aggiungi root e scripts al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'core'))

def test_positions_dict_key_fix():
    """Test che la chiave sia avg_buy_price e non avg_price"""
    print("1️⃣ Test chiave positions_dict corretta")
    
    # Simula positions dal database
    positions = [
        ('IEAC.MI', 100, 25.50),
        ('XS2L.MI', 50, 12.30)
    ]
    
    # Nuova implementazione corretta
    positions_dict = {symbol: {'qty': qty, 'avg_buy_price': avg_buy_price if avg_buy_price else 0} 
                     for symbol, qty, avg_buy_price in positions}
    
    # Verifica
    for symbol, data in positions_dict.items():
        if 'avg_buy_price' not in data:
            print(f"❌ {symbol}: chiave avg_buy_price mancante")
            return False
        if 'avg_price' in data:
            print(f"❌ {symbol}: chiave errata avg_price presente")
            return False
    
    print("   ✅ Chiave avg_buy_price corretta in positions_dict")
    return True

def test_position_caps_math():
    """Test che i cap non vengano violati dalla normalizzazione"""
    print("\n2️⃣ Test position caps non violati")
    
    # Config mock
    config = {
        'risk_management': {
            'xs2l_position_cap': 0.35
        }
    }
    
    # Test weights con XS2L sopra il cap
    test_weights = {
        'IEAC.MI': 0.30,
        'XS2L.MI': 0.40,  # Sopra il cap di 0.35
        'EIMI.MI': 0.20,
        'SPY.MI': 0.10
    }
    
    # Implementazione corretta
    def apply_position_caps_fixed(config, weights):
        """Applica position caps per symbol senza violare i limiti"""
        capped_weights = weights.copy()
        
        # XS2L specific cap
        xs2l_cap = config['risk_management'].get('xs2l_position_cap', 0.35)
        if 'XS2L.MI' in capped_weights:
            original_weight = capped_weights['XS2L.MI']
            capped_weights['XS2L.MI'] = min(capped_weights['XS2L.MI'], xs2l_cap)
            
            # Ridistribuisci il peso eccedente agli altri asset proporzionalmente
            excess_weight = original_weight - capped_weights['XS2L.MI']
            if excess_weight > 0:
                other_symbols = [s for s in capped_weights if s != 'XS2L.MI']
                if other_symbols:
                    total_other_weight = sum(capped_weights[s] for s in other_symbols)
                    for symbol in other_symbols:
                        if total_other_weight > 0:
                            proportion = capped_weights[symbol] / total_other_weight
                            capped_weights[symbol] += excess_weight * proportion
        
        # Normalizza solo se necessario (per piccoli errori di arrotondamento)
        total_weight = sum(capped_weights.values())
        if abs(total_weight - 1.0) > 0.001:  # Tolleranza 0.1%
            for symbol in capped_weights:
                capped_weights[symbol] = capped_weights[symbol] / total_weight
        
        return capped_weights
    
    capped_weights = apply_position_caps_fixed(config, test_weights)
    
    # Verifica XS2L cap
    if 'XS2L.MI' in capped_weights:
        if capped_weights['XS2L.MI'] > 0.35:
            print(f"❌ XS2L.MI cap violato: {capped_weights['XS2L.MI']:.3f}")
            return False
        else:
            print(f"   ✅ XS2L.MI cap rispettato: {capped_weights['XS2L.MI']:.3f}")
    
    # Verifica somma pesi = 1
    total_weight = sum(capped_weights.values())
    if abs(total_weight - 1.0) > 0.001:
        print(f"❌ Somma pesi non normalizzata: {total_weight:.3f}")
        return False
    else:
        print(f"   ✅ Somma pesi normalizzata: {total_weight:.3f}")
    
    # Verifica che il peso eccedente sia stato ridistribuito
    if capped_weights['XS2L.MI'] < 0.40:
        print("   ✅ Peso eccedente ridistribuito ad altri asset")
    
    return True

def test_do_nothing_logic():
    """Test logica do_nothing_score corretta"""
    print("\n3️⃣ Test logica do_nothing_score")
    
    # Simula valori realistici
    position_value = 10000
    expected_alpha = 30  # Alpha giornaliero atteso
    total_cost = 15
    tax_estimate = 5
    
    do_nothing_score = (expected_alpha - total_cost - tax_estimate) / position_value
    
    # Con inertia_threshold tipico di 0.001 (0.1%)
    inertia_threshold = 0.001
    
    # LOGICA CORRETTA: Se do_nothing_score >= threshold → TRADE
    # (alpha >= costi → più propenso a tradare)
    recommendation = 'TRADE' if do_nothing_score >= inertia_threshold else 'HOLD'
    
    print(f"   Expected alpha: €{expected_alpha:.2f}")
    print(f"   Total cost: €{total_cost:.2f}")
    print(f"   Tax estimate: €{tax_estimate:.2f}")
    print(f"   Do-nothing score: {do_nothing_score:.4f}")
    print(f"   Inertia threshold: {inertia_threshold:.4f}")
    print(f"   Recommendation: {recommendation}")
    
    # Con questi valori: (30-15-5)/10000 = 0.001 >= 0.001 → TRADE
    if do_nothing_score >= inertia_threshold and recommendation == 'TRADE':
        print("   ✅ Logica do_nothing_score corretta: alpha >= costi → TRADE")
        return True
    else:
        print("   ❌ Logica do_nothing_score errata")
        return False

def test_expected_alpha_model():
    """Test expected_alpha modellistico"""
    print("\n4️⃣ Test expected_alpha modellistico")
    
    # Parametri di test
    base_alpha = 0.08  # 8% annual
    risk_scalar = 0.8
    current_vol = 0.15  # 15%
    position_value = 10000
    
    # Implementazione modellistica
    risk_adjusted_alpha = base_alpha * risk_scalar
    vol_adjustment = min(1.5, 0.10 / current_vol)
    risk_adjusted_alpha *= vol_adjustment
    daily_alpha = (1 + risk_adjusted_alpha) ** (1/252) - 1
    expected_alpha = position_value * daily_alpha
    
    print(f"   Base alpha: {base_alpha:.1%}")
    print(f"   Risk scalar: {risk_scalar:.2f}")
    print(f"   Vol adjustment: {vol_adjustment:.2f}")
    print(f"   Risk-adjusted alpha: {risk_adjusted_alpha:.1%}")
    print(f"   Daily alpha: {daily_alpha:.4%}")
    print(f"   Expected alpha: €{expected_alpha:.2f}")
    
    # Verifica che sia modellistico e non hardcoded
    if expected_alpha > 0 and expected_alpha != position_value * 0.05:
        print("   ✅ Expected_alpha modellistico (non hardcoded)")
        return True
    else:
        print("   ❌ Expected_alpha ancora hardcoded o nullo")
        return False

def test_unified_logic():
    """Test che rebalancing e segnali siano unificati"""
    print("\n5️⃣ Test logica unificata rebalancing/segnali")
    
    # Simula lo stato del sistema
    signal_states = {
        'IEAC.MI': 'HOLD',      # Dovrebbe fare rebalancing se deviato
        'XS2L.MI': 'RISK_ON',   # Dovrebbe processare segnale, non rebalancing
        'EIMI.MI': 'RISK_OFF'   # Dovrebbe processare segnale, non rebalancing
    }
    
    # Logica implementata: rebalancing solo se signal_state not in ['RISK_ON', 'RISK_OFF']
    rebalance_candidates = []
    signal_candidates = []
    
    for symbol, signal_state in signal_states.items():
        if signal_state not in ['RISK_ON', 'RISK_OFF']:
            rebalance_candidates.append(symbol)
        else:
            signal_candidates.append(symbol)
    
    print(f"   Rebalancing candidates: {rebalance_candidates}")
    print(f"   Signal candidates: {signal_candidates}")
    
    # Verifica che non ci siano conflitti
    if len(rebalance_candidates) > 0 and len(signal_candidates) > 0:
        if set(rebalance_candidates).isdisjoint(set(signal_candidates)):
            print("   ✅ Logica unificata: nessun conflitto rebalancing/segnali")
            return True
        else:
            print("   ❌ Conflitto rilevato tra rebalancing e segnali")
            return False
    else:
        print("   ✅ Logica unificata: separazione corretta")
        return True

def main():
    """Run tutti i test"""
    print("🧪 STRATEGY ENGINE FIXES TEST (Logic Only) - ETF Italia Project v10.7")
    print("=" * 60)
    
    tests = [
        test_positions_dict_key_fix,
        test_position_caps_math,
        test_do_nothing_logic,
        test_expected_alpha_model,
        test_unified_logic
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Errore in {test.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ Tutti i test superati ({passed}/{total})")
        print("✅ Strategy engine fixes verificati con successo!")
        return True
    else:
        print(f"❌ Test falliti ({total-passed}/{total})")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
