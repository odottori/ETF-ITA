#!/usr/bin/env python3
"""
Backup Database - ETF Italia Project v10.8
Backup automatico pre-commit con timestamp e validazione
"""

import sys
import os
import shutil
from datetime import datetime
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager


def backup_database(reason="manual"):
    """
    Esegue backup del database con timestamp
    
    Args:
        reason: Motivo del backup (manual, pre_commit, scheduled, etc.)
    
    Returns:
        tuple: (success: bool, backup_path: str, message: str)
    """
    
    print("💾 DATABASE BACKUP")
    print("=" * 60)
    
    pm = get_path_manager()
    
    # Path database sorgente
    db_source = pm.db_path
    
    if not db_source.exists():
        error_msg = f"❌ Database non trovato: {db_source}"
        print(error_msg)
        return False, None, error_msg
    
    # Ottieni dimensione DB
    db_size_mb = db_source.stat().st_size / (1024 * 1024)
    
    print(f"Database: {db_source.name}")
    print(f"Size: {db_size_mb:.2f} MB")
    print(f"Reason: {reason}")
    
    # Genera timestamp e path backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = pm.db_backup_path(timestamp)
    
    # Assicura che la directory backups esista
    pm.ensure_parent_dir(backup_path)
    
    try:
        # Esegui backup (copia file)
        print(f"\n📋 Copying database...")
        shutil.copy2(db_source, backup_path)
        
        # Verifica backup
        if not backup_path.exists():
            error_msg = "❌ Backup fallito: file non creato"
            print(error_msg)
            return False, None, error_msg
        
        backup_size_mb = backup_path.stat().st_size / (1024 * 1024)
        
        if backup_size_mb != db_size_mb:
            error_msg = f"❌ Backup corrotto: size mismatch ({backup_size_mb:.2f} MB vs {db_size_mb:.2f} MB)"
            print(error_msg)
            backup_path.unlink()  # Rimuovi backup corrotto
            return False, None, error_msg
        
        # Successo
        success_msg = f"✅ Backup completato: {backup_path.name}"
        print(f"\n{success_msg}")
        print(f"Backup size: {backup_size_mb:.2f} MB")
        print(f"Backup path: {backup_path}")
        
        # Cleanup vecchi backup (mantieni ultimi 10)
        cleanup_old_backups(pm, keep_last=10)
        
        return True, str(backup_path), success_msg
        
    except Exception as e:
        error_msg = f"❌ Errore durante backup: {e}"
        print(error_msg)
        return False, None, error_msg


def cleanup_old_backups(pm, keep_last=10):
    """
    Rimuove vecchi backup mantenendo solo gli ultimi N
    
    Args:
        pm: PathManager instance
        keep_last: Numero di backup da mantenere
    """
    
    backups_dir = pm.db_path.parent / 'backups'
    
    if not backups_dir.exists():
        return
    
    # Lista tutti i backup
    backups = sorted(backups_dir.glob('etf_data_backup_*.duckdb'))
    
    if len(backups) <= keep_last:
        return
    
    # Rimuovi i più vecchi
    to_remove = backups[:-keep_last]
    
    print(f"\n🧹 Cleanup vecchi backup ({len(to_remove)} file)...")
    
    for backup in to_remove:
        try:
            backup.unlink()
            print(f"   Rimosso: {backup.name}")
        except Exception as e:
            print(f"   ⚠️  Errore rimozione {backup.name}: {e}")


def list_backups():
    """Lista tutti i backup disponibili"""
    
    pm = get_path_manager()
    backups_dir = pm.db_path.parent / 'backups'
    
    if not backups_dir.exists():
        print("❌ Directory backups non trovata")
        return []
    
    backups = sorted(backups_dir.glob('etf_data_backup_*.duckdb'), reverse=True)
    
    if not backups:
        print("📁 Nessun backup trovato")
        return []
    
    print("📁 BACKUP DISPONIBILI")
    print("=" * 60)
    
    for i, backup in enumerate(backups, 1):
        size_mb = backup.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{i}. {backup.name}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Date: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    return backups


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Database backup utility')
    parser.add_argument('--reason', default='manual', help='Backup reason')
    parser.add_argument('--list', action='store_true', help='List available backups')
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    else:
        success, backup_path, message = backup_database(reason=args.reason)
        sys.exit(0 if success else 1)
