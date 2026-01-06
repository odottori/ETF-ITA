#!/usr/bin/env python3
"""
Update Tax Loss Carryforward - ETF Italia Project v10
Aggiorna used_amount nei record zainetto quando utilizzati
"""

import sys
import os
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def update_zainetto_usage(symbol, tax_category, used_amount, realize_date, conn):
    """Aggiorna used_amount per zainetto utilizzato (FIFO)"""
    
    if used_amount <= 0:
        return
    
    # Seleziona zainetti disponibili per categoria (ordinati per scadenza FIFO)
    available_zainetti = conn.execute("""
        SELECT id, loss_amount, used_amount
        FROM tax_loss_carryforward 
        WHERE tax_category = ? 
        AND used_amount < ABS(loss_amount)
        AND expires_at > ?
        ORDER BY expires_at ASC, id ASC
    """, [tax_category, realize_date]).fetchall()
    
    remaining_to_use = used_amount
    
    for zainetto in available_zainetti:
        if remaining_to_use <= 0:
            break
            
        zainetto_id = zainetto[0]
        loss_amount = zainetto[1]  # Negativo
        current_used = zainetto[2]
        
        available_capacity = abs(loss_amount) - current_used
        
        if available_capacity > 0:
            use_this_time = min(remaining_to_use, available_capacity)
            new_used = current_used + use_this_time
            
            # Aggiorna record
            conn.execute("""
                UPDATE tax_loss_carryforward 
                SET used_amount = ?
                WHERE id = ?
            """, [new_used, zainetto_id])
            
            remaining_to_use -= use_this_time
            
            print(f"    Zainetto {zainetto_id}: +€{use_this_time:.2f} usato (totale: €{new_used:.2f})")
    
    if remaining_to_use > 0.01:
        print(f"    WARNING: Zainetto insufficiente, rimanente: €{remaining_to_use:.2f}")

def test_zainetto_update():
    """Test aggiornamento zainetto"""
    
    print("🧾 ZAINETTO UPDATE TEST - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # Test scenario
        test_date = datetime(2026, 1, 5).date()
        
        # Simula utilizzo zainetto
        print(" Test aggiornamento zainetto...")
        update_zainetto_usage('TEST_ETC', 'ETC', 300.0, test_date, conn)
        
        print("✅ Test completato")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = test_zainetto_update()
    sys.exit(0 if success else 1)
