#!/usr/bin/env python3
"""
Test Strategy Engine Query - ETF Italia Project v10
Verifica che strategy_engine.py possa eseguire query su risk_metrics con close/volume
"""

import sys
import os
import duckdb

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_strategy_engine_query():
    """Test query strategy_engine su risk_metrics"""
    assert _run_strategy_engine_query()


def _run_strategy_engine_query():
    """Runner che ritorna bool (per __main__)."""
    
    print(" TEST STRATEGY ENGINE QUERY")
    print("=" * 50)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db', 'etf_data.duckdb')
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        # Simula la query esatta di strategy_engine.py riga 72-74
        print("Test query strategy_engine.py...")
        
        strategy_query = """
        SELECT close, adj_close, volume, volatility_20d
        FROM risk_metrics 
        WHERE symbol = ? AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = ?)
        """
        
        # Test con simbolo fittizio
        symbol = 'TEST_SYMBOL'
        
        try:
            result = conn.execute(strategy_query, [symbol, symbol]).fetchone()
            print(f"✅ Query eseguita con successo (nessun dato per {symbol} è normale)")
            
            # Verifica che le colonne siano accessibili
            columns = [desc[0] for desc in conn.description]
            expected_columns = ['close', 'adj_close', 'volume', 'volatility_20d']
            
            if columns == expected_columns:
                print(f"✅ Colonne corrette: {columns}")
            else:
                print(f"❌ Colonne errate. Atteso: {expected_columns}, Trovato: {columns}")
                return False
                
        except Exception as e:
            print(f"❌ Errore query: {e}")
            return False
        
        print("\n✅ TEST STRATEGY ENGINE QUERY COMPLETATO")
        return True
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = _run_strategy_engine_query()
    sys.exit(0 if success else 1)
