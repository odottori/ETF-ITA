#!/usr/bin/env python3
"""
Schema Migration v2.0 - Aggiunge colonne audit e tabelle holding period
"""

import sys
import os
import duckdb
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.path_manager import get_path_manager

def migrate_schema():
    """Migra schema esistente a v2.0"""
    
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    conn = duckdb.connect(db_path)
    
    try:
        print(f"Migrazione schema v2.0: {db_path}")
        print("=" * 60)
        
        # 1. Aggiungi colonne audit a fiscal_ledger (se non esistono)
        print("\n1. Aggiornamento fiscal_ledger...")
        
        # Check colonne esistenti
        existing_cols = conn.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'fiscal_ledger'
        """).fetchall()
        existing_cols = [c[0] for c in existing_cols]
        
        if 'decision_path' not in existing_cols:
            conn.execute("ALTER TABLE fiscal_ledger ADD COLUMN decision_path VARCHAR DEFAULT 'LEGACY'")
            print("  ✅ Aggiunta colonna decision_path")
        
        if 'reason_code' not in existing_cols:
            conn.execute("ALTER TABLE fiscal_ledger ADD COLUMN reason_code VARCHAR DEFAULT 'LEGACY_ORDER'")
            print("  ✅ Aggiunta colonna reason_code")
        
        if 'execution_price_mode' not in existing_cols:
            conn.execute("ALTER TABLE fiscal_ledger ADD COLUMN execution_price_mode VARCHAR DEFAULT 'CLOSE_SAME_DAY_SLIPPAGE'")
            print("  ✅ Aggiunta colonna execution_price_mode")
        
        if 'source_order_id' not in existing_cols:
            conn.execute("ALTER TABLE fiscal_ledger ADD COLUMN source_order_id INTEGER")
            print("  ✅ Aggiunta colonna source_order_id")
        
        # Aggiorna run_id a NOT NULL con default per righe esistenti
        if 'run_id' in existing_cols:
            conn.execute("""
            UPDATE fiscal_ledger 
            SET run_id = 'legacy_' || CAST(id AS VARCHAR)
            WHERE run_id IS NULL
            """)
            print("  ✅ Aggiornato run_id per righe legacy")
        
        # 2. Crea nuove tabelle (se non esistono)
        print("\n2. Creazione nuove tabelle...")
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders_plan (
            id INTEGER PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            side VARCHAR NOT NULL CHECK (side IN ('BUY', 'SELL', 'HOLD')),
            qty DOUBLE NOT NULL CHECK (qty >= 0),
            status VARCHAR NOT NULL CHECK (status IN ('TRADE', 'HOLD', 'REJECTED')),
            execution_price_mode VARCHAR NOT NULL DEFAULT 'CLOSE_SAME_DAY_SLIPPAGE',
            proposed_price DOUBLE CHECK (proposed_price >= 0),
            candidate_score DOUBLE CHECK (candidate_score >= 0 AND candidate_score <= 1),
            decision_path VARCHAR NOT NULL,
            reason_code VARCHAR NOT NULL,
            reject_reason VARCHAR,
            config_snapshot_hash VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("  ✅ Tabella orders_plan")
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS position_plans (
            symbol VARCHAR PRIMARY KEY,
            is_open BOOLEAN NOT NULL DEFAULT TRUE,
            entry_date DATE NOT NULL,
            entry_run_id VARCHAR NOT NULL,
            entry_price DOUBLE NOT NULL CHECK (entry_price > 0),
            holding_days_target INTEGER NOT NULL CHECK (holding_days_target >= 30 AND holding_days_target <= 180),
            expected_exit_date DATE NOT NULL,
            last_review_date DATE,
            current_score DOUBLE CHECK (current_score >= 0 AND current_score <= 1),
            plan_status VARCHAR DEFAULT 'ACTIVE' CHECK (plan_status IN ('ACTIVE', 'EXTENDED', 'CLOSING', 'CLOSED')),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("  ✅ Tabella position_plans")
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS position_events (
            event_id INTEGER PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL CHECK (event_type IN (
                'ENTRY_PLANNED', 'ENTRY_EXECUTED', 
                'HOLDING_EXTENDED', 'HOLDING_REVIEWED',
                'EXIT_PLANNED', 'EXIT_EXECUTED', 'EXIT_FORCED'
            )),
            from_exit_date DATE,
            to_exit_date DATE,
            reason_code VARCHAR NOT NULL,
            payload_json VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("  ✅ Tabella position_events")
        
        # 3. Crea indici
        print("\n3. Creazione indici...")
        
        indici = [
            "CREATE INDEX IF NOT EXISTS idx_fiscal_ledger_run_id ON fiscal_ledger(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_fiscal_ledger_decision_path ON fiscal_ledger(decision_path)",
            "CREATE INDEX IF NOT EXISTS idx_orders_plan_run_id ON orders_plan(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_plan_date_symbol ON orders_plan(date, symbol)",
            "CREATE INDEX IF NOT EXISTS idx_orders_plan_status ON orders_plan(status)",
            "CREATE INDEX IF NOT EXISTS idx_position_plans_is_open ON position_plans(is_open)",
            "CREATE INDEX IF NOT EXISTS idx_position_events_run_id ON position_events(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_position_events_symbol_date ON position_events(symbol, date)"
        ]
        
        for idx in indici:
            try:
                conn.execute(idx)
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"  ⚠️  {idx}: {e}")
        
        print("  ✅ Indici creati")
        
        conn.commit()
        print("\n✅ Migrazione completata con successo!")
        return True
        
    except Exception as e:
        print(f"\n❌ Errore durante migrazione: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate_schema()
    sys.exit(0 if success else 1)
