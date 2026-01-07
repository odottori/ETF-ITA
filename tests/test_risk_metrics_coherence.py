#!/usr/bin/env python3
"""
Test Risk Metrics Coherence - ETF Italia Project v10
Verifica che risk_metrics includa close/volume e sia coerente con strategy_engine
"""

import sys
import os
import duckdb

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_risk_metrics_coherence():
    """Test coerenza risk_metrics con strategy_engine"""
    assert _run_risk_metrics_coherence()


def _run_risk_metrics_coherence():
    """Runner che ritorna bool (per __main__)."""
    
    print(" TEST RISK METRICS COHERENCE")
    print("=" * 50)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Verifica che risk_metrics esista
        print("1. Verifica esistenza view risk_metrics...")
        
        result = conn.execute("""
        SELECT COUNT(*) as view_exists 
        FROM information_schema.views 
        WHERE table_name = 'risk_metrics'
        """).fetchone()
        
        if result[0] == 0:
            print("❌ View risk_metrics non esiste")
            return False
        
        print("✅ View risk_metrics esiste")
        
        # 2. Verifica colonne close e volume presenti
        print("\n2. Verifica colonne close e volume...")
        
        columns = conn.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'risk_metrics'
        ORDER BY ordinal_position
        """).fetchall()
        
        column_names = [col[0] for col in columns]
        print(f"   Colonne trovate: {column_names}")
        
        required_columns = ['close', 'volume']
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            print(f"❌ Colonne mancanti: {missing_columns}")
            return False
        
        print("✅ Colonne close e volume presenti")
        
        # 3. Test query strategy_engine
        print("\n3. Test query strategy_engine...")
        
        # Simula la query di strategy_engine
        test_query = """
        SELECT close, adj_close, volume, volatility_20d
        FROM risk_metrics 
        WHERE symbol = ? AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = ?)
        """
        
        # Prova con un simbolo comune
        symbol = 'IE00B4WXJJ64'  # IE00B4WXJJ64 è un comune ETF
        
        try:
            result = conn.execute(test_query, [symbol, symbol]).fetchone()
            
            if result:
                print(f"✅ Query strategy_engine funziona per {symbol}")
                print(f"   close: {result[0]}, adj_close: {result[1]}, volume: {result[2]}, vol: {result[3]}")
            else:
                print(f"⚠️  Nessun dato per {symbol} (potrebbe essere normale)")
                
        except Exception as e:
            print(f"❌ Errore query strategy_engine: {e}")
            return False
        
        # 4. Verifica coerenza dati
        print("\n4. Verifica coerenza dati...")
        
        # Verifica che close e adj_close siano diversi (come previsto)
        consistency_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN close != adj_close THEN 1 END) as different_prices,
            COUNT(CASE WHEN volume > 0 THEN 1 END) as positive_volume
        FROM risk_metrics
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        """
        
        result = conn.execute(consistency_query).fetchone()
        
        if result:
            total, different, positive_vol = result
            print(f"   Record ultimi 30 giorni: {total}")
            print(f"   Prezzi diversi (close != adj_close): {different}")
            print(f"   Volume > 0: {positive_vol}")
            
            if total > 0 and different > 0:
                print("✅ Dati coerenti (close e adj_close diversi come previsto)")
            else:
                print("⚠️  Potenziale incoerenza nei dati")
        
        print("\n✅ TEST RISK METRICS COHERENCE COMPLETATO")
        return True
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = _run_risk_metrics_coherence()
    sys.exit(0 if success else 1)
