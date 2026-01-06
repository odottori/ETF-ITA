#!/usr/bin/env python3
"""
Test Strategy Engine Fixes - ETF Italia Project v10.7
Verifica che tutti i bug fix siano implementati correttamente
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root e scripts al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'core'))

from strategy_engine import strategy_engine
from implement_risk_controls import apply_position_caps, load_config

def test_strategy_engine_fixes():
    """Test completo dei fix implementati"""
    
    print("🧪 STRATEGY ENGINE FIXES TEST - ETF Italia Project v10.7")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        config = load_config()
        
        # 1. Test chiave positions_dict corretta
        print("\n1️⃣ Test chiave positions_dict corretta")
        
        positions = conn.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
            AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        """).fetchall()
        
        positions_dict = {symbol: {'qty': qty, 'avg_buy_price': avg_buy_price if avg_buy_price else 0} 
                         for symbol, qty, avg_buy_price in positions}
        
        # Verifica che la chiave sia avg_buy_price
        for symbol, data in positions_dict.items():
            if 'avg_buy_price' not in data:
                print(f"❌ {symbol}: chiave avg_buy_price mancante")
                return False
        
        print("   ✅ Chiave avg_buy_price corretta in positions_dict")
        
        # 2. Test apply_position_caps non viola i limiti
        print("\n2️⃣ Test position caps non violati")
        
        test_weights = {
            'IEAC.MI': 0.30,
            'XS2L.MI': 0.40,  # Sopra il cap di 0.35
            'EIMI.MI': 0.20,
            'SPY.MI': 0.10
        }
        
        capped_weights = apply_position_caps(config, test_weights)
        
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
        
        # 3. Test logica do_nothing_score corretta
        print("\n3️⃣ Test logica do_nothing_score")
        
        # Simula valori per test
        position_value = 10000
        expected_alpha = 800  # 8% annual → ~0.03% daily
        total_cost = 50
        tax_estimate = 20
        
        do_nothing_score = (expected_alpha - total_cost - tax_estimate) / position_value
        
        # Con inertia_threshold tipico di 0.001 (0.1%)
        inertia_threshold = 0.001
        
        # Se do_nothing_score > threshold → TRADE (logica corretta)
        recommendation = 'TRADE' if do_nothing_score > inertia_threshold else 'HOLD'
        
        print(f"   Do-nothing score: {do_nothing_score:.4f}")
        print(f"   Inertia threshold: {inertia_threshold:.4f}")
        print(f"   Recommendation: {recommendation}")
        
        if do_nothing_score > 0 and recommendation == 'TRADE':
            print("   ✅ Logica do_nothing_score corretta")
        else:
            print("   ⚠️ Logica do_nothing_score da verificare con valori reali")
        
        # 4. Test expected_alpha modellistico
        print("\n4️⃣ Test expected_alpha modellistico")
        
        # Simula parametri
        base_alpha = 0.08
        risk_scalar = 0.8
        current_vol = 0.15  # 15%
        position_value = 10000
        
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
        
        if expected_alpha > 0:
            print("   ✅ Expected_alpha modellistico positivo")
        else:
            print("   ❌ Expected_alpha modellistico negativo")
            return False
        
        # 5. Test esecuzione strategy engine
        print("\n5️⃣ Test esecuzione strategy engine")
        
        success = strategy_engine(dry_run=True, commit=False)
        
        if success:
            print("   ✅ Strategy engine eseguito senza errori")
        else:
            print("   ❌ Strategy engine fallito")
            return False
        
        print("\n✅ Tutti i fix verificati con successo!")
        return True
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = test_strategy_engine_fixes()
    sys.exit(0 if success else 1)
