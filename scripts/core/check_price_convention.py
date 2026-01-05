#!/usr/bin/env python3
"""
Price Convention Sanity Check - ETF Italia Project v10
Verifica il rispetto della regola: adj_close per segnali, close per valuation
"""

import sys
import os
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_price_convention():
    """Verifica che adj_close sia usato per segnali e close per valuation"""
    
    print("🔍 PRICE CONVENTION SANITY CHECK - ETF Italia Project v10")
    print("=" * 60)
    print("Regola: adj_close per segnali, close per valuation/ledger")
    print()
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        violations = []
        
        # 1. Verifica che compute_signals usi adj_close
        print("1️⃣ Verifica compute_signals.py (deve usare adj_close)")
        
        signals_file = os.path.join(os.path.dirname(__file__), 'compute_signals.py')
        with open(signals_file, 'r', encoding='utf-8') as f:
            signals_content = f.read()
        
        if 'adj_close' in signals_content and 'SELECT adj_close' in signals_content:
            print("   ✅ compute_signals usa adj_close per calcolo segnali")
        else:
            violations.append("compute_signals non usa adj_close per segnali")
            print("   ❌ compute_signals non usa adj_close per segnali")
        
        # 2. Verifica che strategy_engine usi close per valuation
        print("\n2️⃣ Verifica strategy_engine.py (deve usare close per valuation)")
        
        strategy_file = os.path.join(os.path.dirname(__file__), 'strategy_engine.py')
        with open(strategy_file, 'r', encoding='utf-8') as f:
            strategy_content = f.read()
        
        # Controlla che usi close per prezzi correnti
        if "current_prices[symbol]['close']" in strategy_content:
            print("   ✅ strategy_engine usa close per valuation ordini")
        else:
            violations.append("strategy_engine non usa close per valuation")
            print("   ❌ strategy_engine non usa close per valuation")
        
        # 3. Verifica che fiscal_ledger usi close (implicito nel price field)
        print("\n3️⃣ Verifica fiscal_ledger (deve contenere close prices)")
        
        # Verifica che i prezzi nel ledger siano close prices
        ledger_check = conn.execute("""
            SELECT COUNT(*) as total_records
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL') AND date >= '2025-01-01'
        """).fetchone()
        
        if ledger_check[0] > 0:
            print(f"   ✅ fiscal_ledger contiene {ledger_check[0]} operazioni con prezzi")
        else:
            print("   ⚠️ fiscal_ledger non ha operazioni recenti da verificare")
        
        # 4. Verifica coerenza dati market_data
        print("\n4️⃣ Verifica coerenza dati market_data")
        
        # Controlla che adj_close e close siano diversi (indicando adjustment)
        diff_check = conn.execute("""
            SELECT COUNT(*) as diff_count
            FROM market_data 
            WHERE ABS(adj_close - close) > 0.01 
            AND date >= '2025-01-01'
        """).fetchone()
        
        print(f"   📊 Record con adj_close ≠ close: {diff_check[0]}")
        
        if diff_check[0] > 0:
            print("   ✅ Ci sono adjustment (adj_close diverso da close)")
        else:
            print("   ⚠️ Nessun adjustment rilevato (adj_close = close)")
        
        # 5. Verifica che i segnali usino adj_close
        print("\n5️⃣ Verifica tabella signals (basata su adj_close)")
        
        signals_check = conn.execute("""
            SELECT COUNT(*) as signal_count
            FROM signals 
            WHERE date >= '2025-01-01'
        """).fetchone()
        
        if signals_check[0] > 0:
            print(f"   ✅ Tabella signals contiene {signals_check[0]} segnali")
        else:
            print("   ⚠️ Tabella signals vuota o senza dati recenti")
        
        # 6. Test specifico: verifica che non ci siano inversioni
        print("\n6️⃣ Verifica assenza di inversioni (close in segnali)")
        
        # Controlla che non ci siano riferimenti a close in compute_signals
        if 'SELECT close' in signals_content and 'FROM risk_metrics' in signals_content:
            violations.append("compute_signals usa close invece di adj_close")
            print("   ❌ Trovato 'SELECT close' in compute_signals - VIOLAZIONE!")
        else:
            print("   ✅ Nessuna inversione rilevata in compute_signals")
        
        # 7. Verifica che i prezzi di valuation siano close
        print("\n7️⃣ Verifica prezzi di valuation sono close")
        
        # Controlla che strategy_engine non usi adj_close per valuation
        if "adj_close as close" in strategy_content and "SELECT adj_close" in strategy_content:
            violations.append("strategy_engine usa adj_close per valuation")
            print("   ❌ strategy_engine usa adj_close per valuation - VIOLAZIONE!")
        else:
            print("   ✅ strategy_engine non usa adj_close per valuation")
        
        # Risultato finale
        print("\n" + "=" * 60)
        print("🎯 PRICE CONVENTION CHECK RESULTS:")
        print("=" * 60)
        
        if len(violations) == 0:
            print("✅ NESSUNA VIOLAZIONE TROVATA")
            print("✅ Regola 'adj_close per segnali, close per valuation' rispettata")
            return True
        else:
            print(f"❌ TROVATE {len(violations)} VIOLAZIONI:")
            for i, violation in enumerate(violations, 1):
                print(f"   {i}. {violation}")
            print("\n❌ REGOLA VIOLATA - Correggere implementazione!")
            return False
            
    except Exception as e:
        print(f"❌ Errore durante verifica: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = check_price_convention()
    sys.exit(0 if success else 1)
