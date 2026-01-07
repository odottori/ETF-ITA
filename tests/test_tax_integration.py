#!/usr/bin/env python3
"""
Tax Integration Test - ETF Italia Project v10
Verifica integrazione completa logica fiscale con ordini/ledger
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_tax_integration():
    """Test integrazione fiscale completa"""
    assert _run_tax_integration()


def _run_tax_integration():
    """Runner che ritorna bool (per __main__)."""
    
    print("🧾 TAX INTEGRATION TEST - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Verifica esistenza DB
    if not os.path.exists(db_path):
        print(f"   ❌ Database non trovato: {db_path}")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Verifica schema tabelle fiscali
        print("1️⃣ Verifica schema tabelle fiscali...")
        
        tables_check = conn.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name IN ('tax_loss_carryforward', 'symbol_registry', 'fiscal_ledger')
        """).fetchall()
        
        expected_tables = {'tax_loss_carryforward', 'symbol_registry', 'fiscal_ledger'}
        found_tables = {row[0] for row in tables_check}
        
        missing = expected_tables - found_tables
        if missing:
            print(f"   ❌ Tabelle mancanti: {missing}")
            return False
        else:
            print("   ✅ Schema tabelle OK")
        
        # 2. Verifica logica zainetto per categoria
        print("\n2️⃣ Verifica logica zainetto per categoria...")
        
        # Import funzioni fiscali
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'core'))
        from implement_tax_logic import calculate_tax, create_tax_loss_carryforward
        
        test_date = datetime(2026, 1, 5).date()
        
        # Test OICR_ETF (no compensazione)
        oicr_result = calculate_tax(1000.0, 'CSSPX.MI', test_date, conn)
        if oicr_result['zainetto_used'] == 0 and oicr_result['tax_amount'] == 260.0:
            print("   ✅ OICR_ETF: tassazione piena corretta")
        else:
            print(f"   ❌ OICR_ETF: tax={oicr_result['tax_amount']}, zainetto={oicr_result['zainetto_used']}")
            return False
        
        # 3. Verifica creazione zainetto
        print("\n3️⃣ Verifica creazione zainetto...")
        
        # Crea loss per test
        zainetto = create_tax_loss_carryforward('TEST_SYMBOL', test_date, -500.0, conn)
        if zainetto['tax_category'] and zainetto['expires_at']:
            print(f"   ✅ Zainetto creato: {zainetto['tax_category']}, scadenza {zainetto['expires_at']}")
        else:
            print("   ❌ Creazione zainetto fallita")
            return False
        
        # 4. Verifica integrazione execute_orders
        print("\n4️⃣ Verifica integrazione execute_orders...")
        
        # Controlla che execute_orders.py importi le funzioni fiscali
        execute_orders_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'core', 'execute_orders.py')
        with open(execute_orders_path, 'r', encoding='utf-8') as f:
            execute_content = f.read()
        
        if 'from implement_tax_logic import' in execute_content:
            print("   ✅ execute_orders.py integra logica fiscale")
        else:
            print("   ❌ execute_orders.py non integra logica fiscale")
            return False
        
        # 5. Verifica coerenza DIPF
        print("\n5️⃣ Verifica coerenza DIPF...")
        
        # Controlla che implement_tax_logic.py usi query per categoria fiscale
        tax_logic_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'core', 'implement_tax_logic.py')
        with open(tax_logic_path, 'r', encoding='utf-8') as f:
            tax_logic_content = f.read()
        
        if 'WHERE tax_category = ?' in tax_logic_content:
            print("   ✅ Query zainetto per categoria fiscale in implement_tax_logic.py")
        else:
            print("   ❌ Query zainetto ancora per simbolo in implement_tax_logic.py")
            return False
        
        # Verifica che le query per simbolo in execute_orders.py siano appropriate (posizioni/prezzi)
        symbol_queries_count = execute_content.count('WHERE symbol = ?')
        if symbol_queries_count >= 2:  # Aspettati: position check e avg_buy_price
            print(f"   ✅ Query per simbolo appropriate in execute_orders.py ({symbol_queries_count} trovate)")
        else:
            print(f"   ⚠️ Query per simbolo: {symbol_queries_count} (attesi ≥2)")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print("🎯 TAX INTEGRATION TEST RESULTS:")
        print("=" * 60)
        print("✅ Schema tabelle fiscali OK")
        print("✅ Logica zainetto per categoria OK")
        print("✅ Creazione zainetto OK")
        print("✅ Integrazione execute_orders OK")
        print("✅ Coerenza DIPF §6.2 OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = _run_tax_integration()
    sys.exit(0 if success else 1)
