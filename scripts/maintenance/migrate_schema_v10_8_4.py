#!/usr/bin/env python3
"""
Schema Migration v10.8.4 - ETF Italia Project
Migra DB esistenti con colonne calendar healing e fix constraint holding_days_target
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from utils.path_manager import get_path_manager


def migrate_schema_v10_8_4():
    """
    Migrazione schema v10.8.4:
    1. Aggiunge 6 colonne calendar healing a trading_calendar
    2. Corregge constraint holding_days_target (5-30 invece di 30-180)
    3. Aggiunge indici per performance
    """
    
    print("\n" + "=" * 70)
    print("🔧 SCHEMA MIGRATION v10.8.4 - ETF Italia Project")
    print("=" * 70)
    
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    # Backup DB prima della migrazione
    backup_path = str(pm.db_backup_path())
    print(f"\n📦 Backup DB in corso...")
    print(f"   Source: {db_path}")
    print(f"   Backup: {backup_path}")
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"   ✅ Backup completato")
    except Exception as e:
        print(f"   ❌ Errore backup: {e}")
        print(f"   ⚠️  Continuare senza backup? (y/n)")
        response = input().strip().lower()
        if response != 'y':
            print("   Migrazione annullata")
            return False
    
    conn = duckdb.connect(db_path)
    
    try:
        print("\n" + "=" * 70)
        print("STEP 1: Migrazione trading_calendar (6 colonne healing)")
        print("=" * 70)
        
        # Check colonne esistenti
        columns = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trading_calendar'
        """).df()['column_name'].tolist()
        
        migrations_needed = []
        
        if 'quality_flag' not in columns:
            migrations_needed.append("quality_flag VARCHAR")
        if 'flagged_at' not in columns:
            migrations_needed.append("flagged_at TIMESTAMP")
        if 'flagged_reason' not in columns:
            migrations_needed.append("flagged_reason TEXT")
        if 'retry_count' not in columns:
            migrations_needed.append("retry_count INTEGER DEFAULT 0")
        if 'last_retry' not in columns:
            migrations_needed.append("last_retry TIMESTAMP")
        if 'healed_at' not in columns:
            migrations_needed.append("healed_at TIMESTAMP")
        
        if migrations_needed:
            print(f"\n📝 Aggiungo {len(migrations_needed)} colonne a trading_calendar...")
            
            for col_def in migrations_needed:
                col_name = col_def.split()[0]
                try:
                    conn.execute(f"ALTER TABLE trading_calendar ADD COLUMN {col_def}")
                    print(f"   ✅ Aggiunta colonna: {col_name}")
                except Exception as e:
                    print(f"   ⚠️  Colonna {col_name}: {e}")
            
            # Crea indici
            try:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trading_calendar_quality_flag 
                    ON trading_calendar(quality_flag) 
                    WHERE quality_flag IS NOT NULL
                """)
                print("   ✅ Creato indice: idx_trading_calendar_quality_flag")
            except Exception as e:
                print(f"   ⚠️  Indice quality_flag: {e}")
            
            try:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trading_calendar_retry_pending 
                    ON trading_calendar(last_retry, retry_count) 
                    WHERE quality_flag IS NOT NULL
                """)
                print("   ✅ Creato indice: idx_trading_calendar_retry_pending")
            except Exception as e:
                print(f"   ⚠️  Indice retry_pending: {e}")
        else:
            print("   ✅ trading_calendar già aggiornato")
        
        print("\n" + "=" * 70)
        print("STEP 2: Fix constraint position_plans.holding_days_target")
        print("=" * 70)
        
        # DuckDB non supporta ALTER CONSTRAINT, dobbiamo ricreare la tabella
        print("\n⚠️  NOTA: DuckDB non supporta ALTER CONSTRAINT")
        print("   Per applicare il fix, è necessario ricreare position_plans")
        print("   Questo richiede:")
        print("   1. Backup dati esistenti")
        print("   2. DROP TABLE position_plans")
        print("   3. CREATE TABLE con constraint corretto")
        print("   4. Restore dati")
        print("\n   Procedere con fix constraint? (y/n)")
        
        response = input().strip().lower()
        
        if response == 'y':
            # Backup dati position_plans
            print("\n📦 Backup dati position_plans...")
            backup_data = conn.execute("SELECT * FROM position_plans").fetchall()
            backup_columns = [desc[0] for desc in conn.execute("PRAGMA table_info('position_plans')").fetchall()]
            print(f"   ✅ Backup {len(backup_data)} record")
            
            # Drop e ricrea tabella
            print("\n🔄 Ricreo position_plans con constraint corretto...")
            conn.execute("DROP TABLE IF EXISTS position_plans")
            
            conn.execute("""
                CREATE TABLE position_plans (
                    symbol VARCHAR PRIMARY KEY,
                    is_open BOOLEAN NOT NULL DEFAULT TRUE,
                    entry_date DATE NOT NULL,
                    entry_run_id VARCHAR NOT NULL,
                    entry_price DOUBLE NOT NULL CHECK (entry_price > 0),
                    holding_days_target INTEGER NOT NULL CHECK (holding_days_target >= 5 AND holding_days_target <= 30),
                    expected_exit_date DATE NOT NULL,
                    last_review_date DATE,
                    current_score DOUBLE CHECK (current_score >= 0 AND current_score <= 1),
                    plan_status VARCHAR DEFAULT 'ACTIVE' CHECK (plan_status IN ('ACTIVE', 'EXTENDED', 'CLOSING', 'CLOSED')),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("   ✅ Tabella ricreata con constraint 5-30 giorni")
            
            # Restore dati (solo se compatibili con nuovo constraint)
            if backup_data:
                print("\n📥 Restore dati...")
                restored = 0
                skipped = 0
                
                for row in backup_data:
                    # Verifica che holding_days_target sia nel range 5-30
                    holding_days_idx = backup_columns.index('holding_days_target')
                    holding_days = row[holding_days_idx]
                    
                    if holding_days and (holding_days < 5 or holding_days > 30):
                        print(f"   ⚠️  Skip {row[0]}: holding_days={holding_days} fuori range")
                        skipped += 1
                        continue
                    
                    # Insert record
                    placeholders = ', '.join(['?'] * len(row))
                    col_list = ', '.join(backup_columns)
                    conn.execute(
                        f"INSERT INTO position_plans ({col_list}) VALUES ({placeholders})",
                        list(row)
                    )
                    restored += 1
                
                print(f"   ✅ Restored {restored} record")
                if skipped > 0:
                    print(f"   ⚠️  Skipped {skipped} record (holding_days fuori range)")
            
            # Ricrea indice
            conn.execute("CREATE INDEX IF NOT EXISTS idx_position_plans_is_open ON position_plans(is_open)")
            print("   ✅ Indice ricreato")
        else:
            print("   ⏭️  Fix constraint skipped")
        
        # Commit modifiche
        conn.commit()
        
        print("\n" + "=" * 70)
        print("✅ MIGRAZIONE COMPLETATA CON SUCCESSO")
        print("=" * 70)
        print(f"\n📊 Riepilogo:")
        print(f"   - trading_calendar: {len(migrations_needed)} colonne aggiunte")
        print(f"   - Indici calendar healing: creati")
        print(f"   - position_plans constraint: {'fixed' if response == 'y' else 'skipped'}")
        print(f"\n💾 Backup disponibile: {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Errore durante migrazione: {e}")
        import traceback
        traceback.print_exc()
        
        print(f"\n🔄 Rollback in corso...")
        try:
            conn.rollback()
            print("   ✅ Rollback completato")
        except:
            pass
        
        print(f"\n💾 Restore backup manuale:")
        print(f"   cp {backup_path} {db_path}")
        
        return False
        
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Schema Migration v10.8.4')
    parser.add_argument('--dry-run', action='store_true', help='Mostra operazioni senza eseguire')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("\n🔍 DRY-RUN MODE")
        print("=" * 70)
        print("Operazioni che verranno eseguite:")
        print("1. Backup DB corrente")
        print("2. Aggiunta 6 colonne a trading_calendar:")
        print("   - quality_flag VARCHAR")
        print("   - flagged_at TIMESTAMP")
        print("   - flagged_reason TEXT")
        print("   - retry_count INTEGER DEFAULT 0")
        print("   - last_retry TIMESTAMP")
        print("   - healed_at TIMESTAMP")
        print("3. Creazione indici calendar healing")
        print("4. Fix constraint position_plans.holding_days_target (5-30)")
        print("\nEseguire migrazione reale:")
        print("   py scripts/maintenance/migrate_schema_v10_8_4.py")
        sys.exit(0)
    
    success = migrate_schema_v10_8_4()
    sys.exit(0 if success else 1)
