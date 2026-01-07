#!/usr/bin/env python3
"""
Test Pre-Trade Controls - ETF Italia Project v10
Verifica controlli pre-trade bloccanti su cash e posizioni
"""

import sys
import os
import json
import duckdb
from datetime import datetime, timedelta
import pytest
import tempfile

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'core'))

def setup_test_data(conn):
    """Setup dati di test per controlli pre-trade"""
    
    print("Setup dati test...")
    
    # Pulisce dati test
    conn.execute("DELETE FROM fiscal_ledger WHERE run_id LIKE 'test_pre_trade_%'")
    
    # Ottiene next ID per evitare conflitti
    next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
    
    # Insert deposito iniziale
    conn.execute(f"""
    INSERT INTO fiscal_ledger 
    (id, date, type, symbol, qty, price, fees, tax_paid, pmc_snapshot, run_id)
    VALUES 
    ({next_id}, CURRENT_DATE - INTERVAL '10 days', 'DEPOSIT', 'CASH', 10000, 1.0, 0, 0, 10000, 'test_pre_trade_setup')
    """)
    
    # Insert posizione esistente
    conn.execute(f"""
    INSERT INTO fiscal_ledger 
    (id, date, type, symbol, qty, price, fees, tax_paid, pmc_snapshot, run_id)
    VALUES 
    ({next_id + 1}, CURRENT_DATE - INTERVAL '5 days', 'BUY', 'IE00B4WXJJ64', 100, 50.0, 5.0, 0, 5005, 'test_pre_trade_setup')
    """)
    
    conn.commit()
    print("✅ Setup completato")


@pytest.fixture(scope='function')
def conn():
    """Connessione DB per test pre-trade (setup + cleanup isolati)."""

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_etf_data.duckdb')
    connection = duckdb.connect(db_path)

    # Schema minimo per execute_orders.check_cash_available/check_position_available
    connection.execute("""
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

    try:
        setup_test_data(connection)
        yield connection
    finally:
        connection.close()
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

def test_cash_insufficient_buy(conn):
    """Test BUY con cash insufficiente"""
    
    print("\n🧪 Test: BUY con cash insufficiente")
    
    from execute_orders import check_cash_available
    
    # Simula ordine BUY che supera cash disponibile
    required_cash = 50000  # Supera i ~25000 disponibili
    
    cash_available, cash_balance = check_cash_available(conn, required_cash)
    
    assert not cash_available, f"Expected cash insufficient, got available: {cash_balance}"
    assert cash_balance < required_cash, f"Expected cash balance < {required_cash}, got {cash_balance}"
    
    print("✅ Test passato: BUY bloccato per cash insufficiente")

def test_cash_sufficient_buy(conn):
    """Test BUY con cash sufficiente"""
    
    print("\n🧪 Test: BUY con cash sufficiente")
    
    from execute_orders import check_cash_available
    
    # Simula ordine BUY entro cash disponibile (con ledger sintetico creato in setup_test_data)
    required_cash = 4000
    
    cash_available, cash_balance = check_cash_available(conn, required_cash)
    
    assert cash_available, f"Expected cash sufficient, got insufficient: {cash_balance}"
    assert cash_balance >= required_cash, f"Expected cash balance >= {required_cash}, got {cash_balance}"
    
    print("✅ Test passato: BUY permesso con cash sufficiente")

def test_position_insufficient_sell(conn):
    """Test SELL con posizione insufficiente"""
    
    print("\n🧪 Test: SELL con posizione insufficiente")
    
    from execute_orders import check_position_available
    
    # Simula vendita che supera posizione disponibile
    required_qty = 150  # Supera i 100 disponibili
    
    position_available, available_qty = check_position_available(conn, 'IE00B4WXJJ64', required_qty)
    
    assert not position_available, f"Expected position insufficient, got available: {available_qty}"
    assert available_qty == 100, f"Expected position 100, got {available_qty}"
    
    print("✅ Test passato: SELL bloccato per posizione insufficiente")

def test_position_sufficient_sell(conn):
    """Test SELL con posizione sufficiente"""
    
    print("\n🧪 Test: SELL con posizione sufficiente")
    
    from execute_orders import check_position_available
    
    # Simula vendita entro posizione disponibile
    required_qty = 50  # Inferiore ai 100 disponibili
    
    position_available, available_qty = check_position_available(conn, 'IE00B4WXJJ64', required_qty)
    
    assert position_available, f"Expected position sufficient, got insufficient: {available_qty}"
    assert available_qty == 100, f"Expected position 100, got {available_qty}"
    
    print("✅ Test passato: SELL permesso con posizione sufficiente")

def test_sell_nonexistent_position(conn):
    """Test SELL su simbolo senza posizione"""
    
    print("\n🧪 Test: SELL su simbolo senza posizione")
    
    from execute_orders import check_position_available
    
    # Simula vendita su simbolo non posseduto
    required_qty = 10
    
    position_available, available_qty = check_position_available(conn, 'NONEXISTENT', required_qty)
    
    assert not position_available, f"Expected position insufficient, got available: {available_qty}"
    assert available_qty == 0, f"Expected position 0, got {available_qty}"
    
    print("✅ Test passato: SELL bloccato per simbolo non posseduto")

def run_pre_trade_tests():
    """Esegue tutti i test pre-trade"""
    
    print(" TEST PRE-TRADE CONTROLS - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # Setup dati test
        setup_test_data(conn)
        
        # Esegui test
        test_cash_insufficient_buy(conn)
        test_cash_sufficient_buy(conn)
        test_position_insufficient_sell(conn)
        test_position_sufficient_sell(conn)
        test_sell_nonexistent_position(conn)
        
        print("\n" + "=" * 60)
        print("✅ TUTTI I TEST PRE-TRADE PASSATI")
        print("✅ Controlli hard su cash e posizioni funzionanti")
        print("✅ Sistema protetto da operazioni impossibili")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test fallito: {e}")
        return False
        
    finally:
        # Cleanup dati test
        try:
            conn.execute("DELETE FROM fiscal_ledger WHERE run_id LIKE 'test_pre_trade_%'")
            conn.commit()
        except:
            pass
        conn.close()

if __name__ == "__main__":
    success = run_pre_trade_tests()
    sys.exit(0 if success else 1)
