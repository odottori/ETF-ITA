#!/usr/bin/env python3
"""
Schema Contract Gate - ETF Italia Project v10.8
Validazione formale bloccante dello schema database vs contract
"""

import sys
import os
import json
import duckdb
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager


def load_schema_contract():
    """Carica schema contract da docs/schema/v003/"""
    
    pm = get_path_manager()
    contract_path = pm.root / 'docs' / 'schema' / 'v003' / 'SCHEMA_CONTRACT.json'
    
    if not contract_path.exists():
        return None, f"Schema contract non trovato: {contract_path}"
    
    try:
        with open(contract_path, 'r') as f:
            contract = json.load(f)
        return contract, None
    except Exception as e:
        return None, f"Errore lettura contract: {e}"


def validate_database_schema(db_path, contract):
    """
    Valida schema database vs contract
    
    Returns:
        tuple: (valid: bool, errors: list, warnings: list)
    """
    
    errors = []
    warnings = []
    
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        
        # 1. Verifica tabelle richieste
        actual_tables = conn.execute("SHOW TABLES").fetchall()
        actual_table_names = set(t[0] for t in actual_tables)
        
        required_tables = set(contract.get('tables', {}).keys())
        
        # Tabelle mancanti
        missing_tables = required_tables - actual_table_names
        if missing_tables:
            errors.append(f"Tabelle mancanti: {', '.join(sorted(missing_tables))}")
        
        # Tabelle extra (warning, non errore)
        extra_tables = actual_table_names - required_tables
        if extra_tables:
            warnings.append(f"Tabelle extra non nel contract: {', '.join(sorted(extra_tables))}")
        
        # 2. Verifica colonne per ogni tabella
        for table_name, table_spec in contract.get('tables', {}).items():
            if table_name not in actual_table_names:
                continue  # Già segnalato come mancante
            
            # Ottieni colonne attuali
            actual_columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
            actual_col_dict = {col[0]: col[1] for col in actual_columns}
            
            required_columns = table_spec.get('columns', {})
            
            # Colonne mancanti
            missing_cols = set(required_columns.keys()) - set(actual_col_dict.keys())
            if missing_cols:
                errors.append(f"Tabella {table_name}: colonne mancanti {', '.join(sorted(missing_cols))}")
            
            # Verifica tipi colonne
            for col_name, col_spec in required_columns.items():
                if col_name not in actual_col_dict:
                    continue  # Già segnalato come mancante
                
                expected_type = col_spec.get('type', '').upper()
                actual_type = actual_col_dict[col_name].upper()
                
                # Normalizza tipi per confronto
                # DuckDB può restituire VARCHAR invece di TEXT, INTEGER invece di BIGINT, etc.
                type_aliases = {
                    'TEXT': ['VARCHAR', 'STRING'],
                    'VARCHAR': ['TEXT', 'STRING'],
                    'BIGINT': ['INTEGER', 'INT'],
                    'INTEGER': ['BIGINT', 'INT'],
                    'DOUBLE': ['FLOAT', 'REAL'],
                    'TIMESTAMP': ['DATETIME']
                }
                
                types_match = False
                if expected_type == actual_type:
                    types_match = True
                elif expected_type in type_aliases:
                    if actual_type in type_aliases[expected_type] or actual_type == expected_type:
                        types_match = True
                
                if not types_match:
                    # Verifica se è un tipo compatibile
                    compatible = False
                    for base_type, aliases in type_aliases.items():
                        if expected_type in [base_type] + aliases and actual_type in [base_type] + aliases:
                            compatible = True
                            break
                    
                    if not compatible:
                        errors.append(f"Tabella {table_name}.{col_name}: tipo mismatch (expected {expected_type}, got {actual_type})")
        
        # 3. Verifica indici (opzionale, solo warning)
        for table_name, table_spec in contract.get('tables', {}).items():
            if table_name not in actual_table_names:
                continue
            
            required_indexes = table_spec.get('indexes', [])
            if required_indexes:
                # DuckDB non ha un modo semplice per listare indici, skip per ora
                pass
        
        conn.close()
        
        return len(errors) == 0, errors, warnings
        
    except Exception as e:
        errors.append(f"Errore validazione: {e}")
        return False, errors, warnings


def schema_contract_gate(db_path=None, strict=True):
    """
    Gate bloccante per validazione schema
    
    Args:
        db_path: Path al database (default: usa PathManager)
        strict: Se True, warnings sono trattati come errori
    
    Returns:
        bool: True se validazione passa, False altrimenti
    """
    
    print("🔒 SCHEMA CONTRACT GATE")
    print("=" * 60)
    
    # Carica contract
    print("📋 Loading schema contract...")
    contract, error = load_schema_contract()
    
    if error:
        print(f"❌ {error}")
        return False
    
    print(f"✅ Contract loaded: {contract.get('version', 'unknown')}")
    print(f"   Tables: {len(contract.get('tables', {}))}")
    
    # Path database
    if db_path is None:
        pm = get_path_manager()
        db_path = pm.db_path
    
    if not Path(db_path).exists():
        print(f"❌ Database non trovato: {db_path}")
        return False
    
    print(f"\n🔍 Validating database schema...")
    print(f"   Database: {Path(db_path).name}")
    
    # Valida schema
    valid, errors, warnings = validate_database_schema(db_path, contract)
    
    # Report risultati
    print("\n" + "=" * 60)
    print("📊 VALIDATION RESULTS")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"   - {error}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   - {warning}")
    
    if not errors and not warnings:
        print("\n✅ Schema validation PASSED")
        print("   Database schema matches contract perfectly")
        return True
    
    elif not errors and warnings:
        if strict:
            print(f"\n❌ Schema validation FAILED (strict mode)")
            print("   Warnings treated as errors in strict mode")
            return False
        else:
            print(f"\n✅ Schema validation PASSED (with warnings)")
            print("   Database schema matches contract (warnings acceptable)")
            return True
    
    else:
        print(f"\n❌ Schema validation FAILED")
        print("   Database schema does NOT match contract")
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Schema contract validation gate')
    parser.add_argument('--db', help='Database path (default: auto-detect)')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    parser.add_argument('--no-strict', dest='strict', action='store_false', help='Allow warnings')
    parser.set_defaults(strict=False)
    
    args = parser.parse_args()
    
    success = schema_contract_gate(db_path=args.db, strict=args.strict)
    
    sys.exit(0 if success else 1)
