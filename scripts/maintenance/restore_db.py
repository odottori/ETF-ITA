#!/usr/bin/env python3
"""
Restore Database - ETF Italia Project v10.8
Ripristino database da backup con validazione e safety checks
"""

import sys
import os
import shutil
import duckdb
from datetime import datetime
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager


def list_available_backups():
    """
    Lista backup disponibili
    
    Returns:
        list: Lista di Path objects per i backup
    """
    pm = get_path_manager()
    backups_dir = pm.db_path.parent / 'backups'
    
    if not backups_dir.exists():
        return []
    
    return sorted(backups_dir.glob('etf_data_backup_*.duckdb'), reverse=True)


def validate_backup(backup_path):
    """
    Valida un file di backup
    
    Args:
        backup_path: Path al file di backup
    
    Returns:
        tuple: (valid: bool, message: str)
    """
    
    if not backup_path.exists():
        return False, "File non trovato"
    
    # Verifica dimensione minima (almeno 1 MB)
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    if size_mb < 1:
        return False, f"File troppo piccolo ({size_mb:.2f} MB)"
    
    # Verifica che sia un database DuckDB valido
    try:
        conn = duckdb.connect(str(backup_path), read_only=True)
        
        # Verifica presenza tabelle essenziali
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        essential_tables = ['market_data', 'signals', 'fiscal_ledger', 'portfolio_overview']
        missing_tables = [t for t in essential_tables if t not in table_names]
        
        conn.close()
        
        if missing_tables:
            return False, f"Tabelle mancanti: {', '.join(missing_tables)}"
        
        return True, f"Backup valido ({size_mb:.2f} MB, {len(table_names)} tabelle)"
        
    except Exception as e:
        return False, f"Database corrotto: {e}"


def restore_database(backup_path, force=False):
    """
    Ripristina database da backup
    
    Args:
        backup_path: Path al file di backup
        force: Se True, salta conferma utente
    
    Returns:
        tuple: (success: bool, message: str)
    """
    
    print("🔄 DATABASE RESTORE")
    print("=" * 60)
    
    pm = get_path_manager()
    db_current = pm.db_path
    
    # Valida backup
    print(f"Backup: {backup_path.name}")
    valid, validation_msg = validate_backup(backup_path)
    
    if not valid:
        error_msg = f"❌ Backup non valido: {validation_msg}"
        print(error_msg)
        return False, error_msg
    
    print(f"✅ {validation_msg}")
    
    # Verifica database corrente
    if db_current.exists():
        current_size_mb = db_current.stat().st_size / (1024 * 1024)
        print(f"\n⚠️  Database corrente verrà sovrascritto!")
        print(f"Current DB: {db_current.name} ({current_size_mb:.2f} MB)")
        
        # Conferma utente (se non force)
        if not force:
            response = input("\n❓ Continuare con il restore? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Restore annullato dall'utente")
                return False, "Restore annullato"
        
        # Backup di sicurezza del DB corrente
        print("\n💾 Creando backup di sicurezza del DB corrente...")
        safety_backup = pm.db_backup_path(datetime.now().strftime("%Y%m%d_%H%M%S") + "_pre_restore")
        pm.ensure_parent_dir(safety_backup)
        shutil.copy2(db_current, safety_backup)
        print(f"✅ Safety backup: {safety_backup.name}")
    
    try:
        # Esegui restore
        print(f"\n📋 Restoring database...")
        shutil.copy2(backup_path, db_current)
        
        # Verifica restore
        if not db_current.exists():
            error_msg = "❌ Restore fallito: database non creato"
            print(error_msg)
            return False, error_msg
        
        restored_size_mb = db_current.stat().st_size / (1024 * 1024)
        
        # Valida database ripristinato
        valid, validation_msg = validate_backup(db_current)
        
        if not valid:
            error_msg = f"❌ Database ripristinato non valido: {validation_msg}"
            print(error_msg)
            
            # Ripristina safety backup
            if 'safety_backup' in locals() and safety_backup.exists():
                print("🔄 Ripristinando safety backup...")
                shutil.copy2(safety_backup, db_current)
                print("✅ Safety backup ripristinato")
            
            return False, error_msg
        
        # Successo
        success_msg = f"✅ Restore completato con successo"
        print(f"\n{success_msg}")
        print(f"Database: {db_current.name}")
        print(f"Size: {restored_size_mb:.2f} MB")
        print(f"Validation: {validation_msg}")
        
        if 'safety_backup' in locals():
            print(f"\n💡 Safety backup disponibile: {safety_backup.name}")
        
        return True, success_msg
        
    except Exception as e:
        error_msg = f"❌ Errore durante restore: {e}"
        print(error_msg)
        
        # Ripristina safety backup
        if 'safety_backup' in locals() and safety_backup.exists():
            print("🔄 Ripristinando safety backup...")
            shutil.copy2(safety_backup, db_current)
            print("✅ Safety backup ripristinato")
        
        return False, error_msg


def interactive_restore():
    """Modalità interattiva per selezione backup"""
    
    backups = list_available_backups()
    
    if not backups:
        print("❌ Nessun backup disponibile")
        return False, "Nessun backup"
    
    print("📁 BACKUP DISPONIBILI")
    print("=" * 60)
    
    for i, backup in enumerate(backups, 1):
        size_mb = backup.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        
        # Valida backup
        valid, msg = validate_backup(backup)
        status = "✅" if valid else "❌"
        
        print(f"{i}. {backup.name} {status}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Date: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: {msg}")
        print()
    
    # Selezione utente
    try:
        choice = input("Seleziona backup da ripristinare (numero o 'q' per uscire): ")
        
        if choice.lower() == 'q':
            print("❌ Restore annullato")
            return False, "Annullato"
        
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(backups):
            print("❌ Selezione non valida")
            return False, "Selezione non valida"
        
        selected_backup = backups[idx]
        return restore_database(selected_backup, force=False)
        
    except ValueError:
        print("❌ Input non valido")
        return False, "Input non valido"
    except KeyboardInterrupt:
        print("\n❌ Restore annullato")
        return False, "Annullato"


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Database restore utility')
    parser.add_argument('--backup', help='Backup file to restore')
    parser.add_argument('--force', action='store_true', help='Skip confirmation')
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    
    args = parser.parse_args()
    
    if args.list:
        backups = list_available_backups()
        if backups:
            print("📁 BACKUP DISPONIBILI")
            print("=" * 60)
            for backup in backups:
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                valid, msg = validate_backup(backup)
                status = "✅" if valid else "❌"
                print(f"{status} {backup.name}")
                print(f"   Size: {size_mb:.2f} MB")
                print(f"   Date: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Status: {msg}")
                print()
        else:
            print("❌ Nessun backup disponibile")
        sys.exit(0)
    
    elif args.interactive:
        success, message = interactive_restore()
        sys.exit(0 if success else 1)
    
    elif args.backup:
        backup_path = Path(args.backup)
        success, message = restore_database(backup_path, force=args.force)
        sys.exit(0 if success else 1)
    
    else:
        # Default: interactive mode
        success, message = interactive_restore()
        sys.exit(0 if success else 1)
