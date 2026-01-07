#!/usr/bin/env python3
"""
Migration: Aggiunge colonne holding period a fiscal_ledger
ETF Italia Project v10
"""

import sys
import os
from pathlib import Path
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.path_manager import get_path_manager

def migrate_fiscal_ledger():
    """Aggiunge colonne holding period a fiscal_ledger esistente"""
    
    pm = get_path_manager()
    db_path = pm.db_path
    
    conn = duckdb.connect(str(db_path))
    
    try:
        print("=" * 80)
        print("MIGRATION: Holding Period Columns → fiscal_ledger")
        print("=" * 80)
        
        # Verifica se le colonne esistono già
        columns = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'fiscal_ledger'
        """).fetchall()
        
        existing_columns = [col[0] for col in columns]
        print(f"\nColonne esistenti: {len(existing_columns)}")
        
        # Colonne da aggiungere
        new_columns = [
            ("entry_date", "DATE"),
            ("entry_score", "DOUBLE"),
            ("expected_holding_days", "INTEGER"),
            ("expected_exit_date", "DATE"),
            ("actual_holding_days", "INTEGER"),
            ("exit_reason", "VARCHAR")
        ]
        
        added_count = 0
        
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                print(f"\n➕ Aggiunta colonna: {col_name} ({col_type})")
                conn.execute(f"ALTER TABLE fiscal_ledger ADD COLUMN {col_name} {col_type}")
                added_count += 1
            else:
                print(f"✓ Colonna già esistente: {col_name}")
        
        conn.commit()
        
        print("\n" + "=" * 80)
        if added_count > 0:
            print(f"✅ Migration completata: {added_count} colonne aggiunte")
        else:
            print("✅ Nessuna modifica necessaria (colonne già presenti)")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Errore durante migration: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate_fiscal_ledger()
    sys.exit(0 if success else 1)
