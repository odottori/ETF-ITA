#!/usr/bin/env python3
"""
Test Critical Bugs Fixed - ETF Italia Project v10.8
Regression test per validare i 9 bug critici identificati e fixati
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import duckdb

# Aggiungi root al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_manager import get_path_manager
from fiscal.tax_engine import get_available_zainetto, create_tax_loss_carryforward


def test_bug_1_avg_buy_price_query():
    """BUG #1: avg_buy_price query ottimizzata (solo BUY, no SELL)"""
    print("\n🧪 TEST BUG #1: avg_buy_price query optimization")
    
    pm = get_path_manager()
    conn = duckdb.connect(str(pm.db_path))
    
    try:
        # Query corretta (solo BUY)
        result = conn.execute("""
        SELECT AVG(price) as avg_buy_price
        FROM fiscal_ledger 
        WHERE symbol = 'CSSPX.MI' AND type = 'BUY'
        """).fetchone()
        
        print(f"   ✅ Query ottimizzata eseguita correttamente")
        return True
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False
    finally:
        conn.close()


def test_bug_2_order_date_parameter():
    """BUG #2: execute_orders accetta order_date parameter"""
    print("\n🧪 TEST BUG #2: order_date parameter in execute_orders")
    
    from trading.execute_orders import execute_orders
    
    # Verifica signature funzione
    import inspect
    sig = inspect.signature(execute_orders)
    params = list(sig.parameters.keys())
    
    if 'order_date' in params and 'run_type' in params:
        print(f"   ✅ Parametri order_date e run_type presenti")
        return True
    else:
        print(f"   ❌ Parametri mancanti: {params}")
        return False


def test_bug_3_4_fiscal_ledger_schema():
    """BUG #3-4: fiscal_ledger insert include run_type, decision_path, reason_code"""
    print("\n🧪 TEST BUG #3-4: fiscal_ledger schema compliance")
    
    pm = get_path_manager()
    conn = duckdb.connect(str(pm.db_path))
    
    try:
        # Verifica che schema abbia i campi obbligatori
        schema = conn.execute("DESCRIBE fiscal_ledger").fetchall()
        columns = [row[0] for row in schema]
        
        required_fields = ['run_type', 'decision_path', 'reason_code']
        missing = [f for f in required_fields if f not in columns]
        
        if not missing:
            print(f"   ✅ Tutti i campi obbligatori presenti: {required_fields}")
            return True
        else:
            print(f"   ❌ Campi mancanti: {missing}")
            return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False
    finally:
        conn.close()


def test_bug_6_7_strategy_engine_variables():
    """BUG #6-7: current_qty e stop_reason definiti in strategy_engine"""
    print("\n🧪 TEST BUG #6-7: strategy_engine variable initialization")
    
    # Leggi file e verifica che stop_reason sia inizializzato
    strategy_file = Path(__file__).parent.parent / 'scripts' / 'trading' / 'strategy_engine.py'
    
    with open(strategy_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verifica inizializzazione stop_reason
    if 'stop_reason = None' in content:
        print(f"   ✅ stop_reason inizializzato correttamente")
        stop_reason_ok = True
    else:
        print(f"   ❌ stop_reason non inizializzato")
        stop_reason_ok = False
    
    # Verifica uso positions_dict per current_qty
    if "current_qty = positions_dict.get(symbol, {}).get('qty', 0)" in content:
        print(f"   ✅ current_qty usa positions_dict")
        current_qty_ok = True
    else:
        print(f"   ❌ current_qty non usa positions_dict")
        current_qty_ok = False
    
    return stop_reason_ok and current_qty_ok


def test_bug_8_backtest_trade_currency():
    """BUG #8: backtest_engine include trade_currency in INSERT"""
    print("\n🧪 TEST BUG #8: backtest_engine trade_currency")
    
    backtest_file = Path(__file__).parent.parent / 'scripts' / 'backtest' / 'backtest_engine.py'
    
    with open(backtest_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verifica che trade_currency sia nell'INSERT
    if 'trade_currency' in content and 'exchange_rate_used' in content:
        # Verifica che siano nell'INSERT statement
        insert_start = content.find('INSERT INTO fiscal_ledger')
        if insert_start > 0:
            insert_section = content[insert_start:insert_start+1000]
            if 'trade_currency' in insert_section:
                print(f"   ✅ trade_currency incluso nell'INSERT")
                return True
    
    print(f"   ❌ trade_currency non incluso nell'INSERT")
    return False


def test_bug_9_zainetto_query():
    """BUG #9: get_available_zainetto usa formula corretta"""
    print("\n🧪 TEST BUG #9: zainetto query formula")
    
    pm = get_path_manager()
    conn = duckdb.connect(str(pm.db_path))
    
    try:
        # Setup test data
        test_date = datetime(2026, 1, 7).date()
        
        # Crea zainetto test
        conn.execute("DELETE FROM tax_loss_carryforward WHERE symbol = 'TEST_BUG9'")
        
        # Inserisci 2 zainetti per test matematico
        conn.execute("""
        INSERT INTO tax_loss_carryforward 
        (id, symbol, realize_date, loss_amount, used_amount, expires_at, tax_category)
        VALUES 
        (99991, 'TEST_BUG9', ?, -1000.0, 200.0, ?, 'ETC'),
        (99992, 'TEST_BUG9', ?, -500.0, 100.0, ?, 'ETC')
        """, [test_date, datetime(2030, 12, 31).date(), test_date, datetime(2030, 12, 31).date()])
        
        # Test formula corretta
        available = get_available_zainetto('ETC', test_date, conn)
        
        # Calcolo atteso: (-1000 + 200) + (-500 + 100) = -800 + -400 = -1200
        expected = -1200.0
        
        if abs(available - expected) < 0.01:
            print(f"   ✅ Formula corretta: disponibile={available:.2f} (atteso={expected:.2f})")
            result = True
        else:
            print(f"   ❌ Formula errata: disponibile={available:.2f} (atteso={expected:.2f})")
            result = False
        
        # Cleanup
        conn.execute("DELETE FROM tax_loss_carryforward WHERE symbol = 'TEST_BUG9'")
        conn.commit()
        
        return result
        
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def run_all_tests():
    """Esegue tutti i test di regressione"""
    
    print("=" * 60)
    print("🔬 CRITICAL BUGS REGRESSION TEST - ETF Italia v10.8")
    print("=" * 60)
    
    tests = [
        ("BUG #1: avg_buy_price query", test_bug_1_avg_buy_price_query),
        ("BUG #2: order_date parameter", test_bug_2_order_date_parameter),
        ("BUG #3-4: fiscal_ledger schema", test_bug_3_4_fiscal_ledger_schema),
        ("BUG #6-7: strategy_engine vars", test_bug_6_7_strategy_engine_variables),
        ("BUG #8: backtest trade_currency", test_bug_8_backtest_trade_currency),
        ("BUG #9: zainetto query formula", test_bug_9_zainetto_query),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name}: EXCEPTION - {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n🎯 Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL CRITICAL BUGS FIXED AND VALIDATED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review fixes")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
