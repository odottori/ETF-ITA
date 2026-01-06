#!/usr/bin/env python3
"""
Test Execute Orders Bridge - ETF Italia Project v10
Test del bridge tra ordini e fiscal_ledger
"""

import sys
import os
import json
import tempfile
import duckdb
from datetime import datetime, date
from decimal import Decimal

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_test_database():
    """Setup database di test"""
    
    # Usa file temporaneo con delete=False per gestire manualmente
    import tempfile
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    # Crea tabelle necessarie
    conn.execute("""
    CREATE TABLE fiscal_ledger (
        id INTEGER PRIMARY KEY,
        date DATE NOT NULL,
        type VARCHAR NOT NULL,
        symbol VARCHAR NOT NULL,
        qty DOUBLE NOT NULL,
        price DOUBLE NOT NULL,
        fees DOUBLE DEFAULT 0.0,
        tax_paid DOUBLE DEFAULT 0.0,
        pmc_snapshot DOUBLE,
        run_id VARCHAR
    )
    """)
    
    conn.execute("""
    CREATE TABLE trade_journal (
        id INTEGER PRIMARY KEY,
        run_id VARCHAR NOT NULL,
        symbol VARCHAR NOT NULL,
        signal_state VARCHAR NOT NULL,
        risk_scalar DOUBLE,
        explain_code VARCHAR,
        flag_override BOOLEAN DEFAULT FALSE,
        override_reason VARCHAR,
        theoretical_price DOUBLE,
        realized_price DOUBLE,
        slippage_bps DOUBLE
    )
    """)
    
    conn.execute("""
    CREATE TABLE risk_metrics (
        symbol VARCHAR,
        date DATE,
        volatility_20d DOUBLE
    )
    """)
    
    # Inserisci dati di test
    test_date = date.today()
    
    # Posizione esistente per test vendita
    conn.execute("""
    INSERT INTO fiscal_ledger 
    (id, date, type, symbol, qty, price, fees, tax_paid, run_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [1, test_date, 'DEPOSIT', 'CASH', 20000, 1.0, 0, 0, 'test_init'])
    
    conn.execute("""
    INSERT INTO fiscal_ledger 
    (id, date, type, symbol, qty, price, fees, tax_paid, run_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [2, test_date, 'BUY', 'IE00B4L5Y983', 100, 50.0, 5.0, 0, 'test_buy'])
    
    # Volatilità per test
    conn.execute("""
    INSERT INTO risk_metrics 
    (symbol, date, volatility_20d)
    VALUES (?, ?, ?)
    """, ['IE00B4L5Y983', test_date, 0.15])
    
    conn.commit()
    return conn, db_path, temp_dir

def create_test_orders():
    """Crea ordini di test"""
    
    orders = [
        {
            'symbol': 'IE00B4L5Y983',
            'action': 'SELL',
            'qty': 50,
            'price': 52.0,
            'reason': 'RISK_OFF_TREND_DOWN',
            'momentum_score': 0.0,
            'fees_est': 2.6,
            'tax_friction_est': 26.0,  # (52-50)*50*0.26
            'trade_score': 0.0,
            'recommendation': 'TRADE',
            'signal_state': 'RISK_OFF',
            'risk_scalar': 0.0
        },
        {
            'symbol': 'IE00B3RBWM25',
            'action': 'BUY',
            'qty': 75,
            'price': 45.0,
            'reason': 'RISK_ON_TREND_UP',
            'momentum_score': 0.8,
            'fees_est': 3.375,
            'tax_friction_est': 0.0,
            'trade_score': 0.7,
            'recommendation': 'TRADE',
            'signal_state': 'RISK_ON',
            'risk_scalar': 0.3
        },
        {
            'symbol': 'IE00B4L5Y983',
            'action': 'HOLD',
            'qty': 0,
            'price': 52.0,
            'reason': 'HOLD_NEUTRAL',
            'momentum_score': 0.0,
            'fees_est': 0.0,
            'tax_friction_est': 0.0,
            'trade_score': 1.0,
            'recommendation': 'HOLD',
            'signal_state': 'HOLD',
            'risk_scalar': 1.0
        }
    ]
    
    return {
        'timestamp': datetime.now().isoformat(),
        'dry_run': False,
        'orders': orders,
        'summary': {
            'total_orders': 3,
            'buy_orders': 1,
            'sell_orders': 1,
            'hold_orders': 1,
            'total_estimated_cost': 31.975,
            'total_momentum_score': 0.4
        }
    }

def test_execute_orders():
    """Test completo del bridge execute_orders"""
    
    print(" TEST EXECUTE ORDERS BRIDGE")
    print("=" * 50)
    
    # Setup test
    conn, db_path, temp_dir = setup_test_database()
    test_orders = create_test_orders()
    
    # Salva ordini in file temporaneo
    orders_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(test_orders, orders_file, indent=2)
    orders_file.close()
    
    try:
        # Import e test
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'core'))
        from execute_orders import execute_orders, validate_orders_file
        
        # 1. Test validazione
        print("\n1. Test validazione file...")
        valid = validate_orders_file(orders_file.name)
        assert valid, "Validazione file fallita"
        print("✅ Validazione OK")
        
        # 2. Test dry-run
        print("\n2. Test dry-run...")
        
        # Mock config path
        original_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
        
        # Crea config di test
        test_config = {
            'universe': {
                'core': [{
                    'cost_model': {
                        'commission_pct': 0.001
                    },
                    'ter': 0.0015
                }]
            },
            'settings': {
                'volatility_target': 0.15
            }
        }
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(test_config, config_file, indent=2)
        config_file.close()
        
        # Override config path
        import execute_orders
        original_path = execute_orders.os.path.join
        execute_orders.os.path.join = lambda *args: config_file.name if 'etf_universe.json' in args else original_path(*args)
        
        # Override db path
        original_db_path = execute_orders.os.path.join
        execute_orders.os.path.join = lambda *args: db_path if 'etf_data.duckdb' in args else original_db_path(*args)
        
        # Esegui dry-run
        success = execute_orders.execute_orders(orders_file=orders_file.name, commit=False)
        assert success, "Dry-run fallito"
        print("✅ Dry-run OK")
        
        # 3. Verifica stato pre-commit
        print("\n3. Verifica stato pre-commit...")
        
        ledger_count = conn.execute("SELECT COUNT(*) FROM fiscal_ledger").fetchone()[0]
        assert ledger_count == 2, f"Attesi 2 record in ledger, trovati {ledger_count}"
        
        journal_count = conn.execute("SELECT COUNT(*) FROM trade_journal").fetchone()[0]
        assert journal_count == 0, f"Attesi 0 record in journal, trovati {journal_count}"
        
        print("✅ Stato pre-commit OK")
        
        # 4. Test commit
        print("\n4. Test commit...")
        
        success = execute_orders.execute_orders(orders_file=orders_file.name, commit=True)
        assert success, "Commit fallito"
        print("✅ Commit OK")
        
        # 5. Verifica stato post-commit
        print("\n5. Verifica stato post-commit...")
        
        # Verifica fiscal_ledger
        ledger_records = conn.execute("""
        SELECT type, symbol, qty, price, fees, tax_paid
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL') AND run_id LIKE 'execute_orders_%'
        ORDER BY id
        """).fetchall()
        
        # Attesi: 1 SELL di 50 IE00B4L5Y983, 1 BUY di 75 IE00B4L5Y983 (solo i nuovi)
        assert len(ledger_records) == 2, f"Attesi 2 record nuovi, trovati {len(ledger_records)}"
        
        sell_record = next((r for r in ledger_records if r[0] == 'SELL'), None)
        assert sell_record is not None, "Record SELL non trovato"
        assert sell_record[1] == 'IE00B4L5Y983', "Symbol SELL errato"
        assert abs(sell_record[2] - 50) < 0.01, "Qty SELL errata"
        
        buy_record = next((r for r in ledger_records if r[0] == 'BUY'), None)
        assert buy_record is not None, "Record BUY non trovato"
        assert buy_record[1] == 'IE00B3RBWM25', "Symbol BUY errato"
        assert abs(buy_record[2] - 75) < 0.01, "Qty BUY errata"
        
        # Verifica trade_journal
        journal_records = conn.execute("""
        SELECT symbol, signal_state, explain_code
        FROM trade_journal 
        ORDER BY id
        """).fetchall()
        
        # Attesi: 2 record (SELL e BUY)
        assert len(journal_records) == 2, f"Attesi 2 record journal, trovati {len(journal_records)}"
        
        print("✅ Stato post-commit OK")
        
        # 6. Test edge cases
        print("\n6. Test edge cases...")
        
        # Ordine con qty insufficiente
        insufficient_orders = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': False,
            'orders': [{
                'symbol': 'IE00B4L5Y983',
                'action': 'SELL',
                'qty': 200,  # Più di quanto posseduto
                'price': 52.0,
                'reason': 'TEST_INSUFFICIENT',
                'momentum_score': 0.0,
                'fees_est': 0.0,
                'tax_friction_est': 0.0,
                'trade_score': 0.0,
                'recommendation': 'TRADE'
            }],
            'summary': {'total_orders': 1}
        }
        
        insufficient_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(insufficient_orders, insufficient_file, indent=2)
        insufficient_file.close()
        
        # Count prima
        count_before = conn.execute("SELECT COUNT(*) FROM fiscal_ledger").fetchone()[0]
        
        success = execute_orders.execute_orders(orders_file=insufficient_file.name, commit=True)
        assert success, "Test insufficient qty fallito"
        
        # Count dopo (non deve cambiare)
        count_after = conn.execute("SELECT COUNT(*) FROM fiscal_ledger").fetchone()[0]
        assert count_before == count_after, "Ordine insufficiente eseguito erroneamente"
        
        print("✅ Edge cases OK")
        
        print(f"\n🎉 TUTTI I TEST SUPERATI")
        
        return True
        
    except Exception as e:
        print(f"❌ Test fallito: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        conn.close()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        os.unlink(orders_file.name)
        if 'config_file' in locals():
            os.unlink(config_file.name)
        if 'insufficient_file' in locals():
            os.unlink(insufficient_file.name)

if __name__ == "__main__":
    success = test_execute_orders()
    sys.exit(0 if success else 1)
