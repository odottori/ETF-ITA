#!/usr/bin/env python3
"""
Schema Drift Analysis - ETF Italia Project v10
Analizza discrepanze tra DATADICTIONARY e implementazione reale
"""

import sys
import os
import duckdb
import json
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_schema_drift():
    """Analizza drift tra DATADICTIONARY e schema reale"""
    
    print("🔍 SCHEMA DRIFT ANALYSIS - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Analizza market_data
        print("1️⃣ Analisi market_data")
        
        # Schema reale
        real_schema = conn.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'market_data'
            ORDER BY ordinal_position
        """).fetchall()
        
        print("   Schema reale:")
        for col, dtype in real_schema:
            print(f"      {col}: {dtype}")
        
        # Schema atteso da DD-2.1
        expected_columns = {
            'symbol': 'VARCHAR',
            'date': 'DATE', 
            'close': 'DOUBLE',
            'adj_close': 'DOUBLE',
            'volume': 'BIGINT',
            'currency': 'VARCHAR',      # MANCANTE
            'provider': 'VARCHAR',      # MANCANTE
            'created_at': 'TIMESTAMP', # MANCANTE
            'last_updated': 'TIMESTAMP' # MANCANTE
        }
        
        real_columns = {col: dtype for col, dtype in real_schema}
        
        missing_columns = []
        extra_columns = []
        
        for col, expected_type in expected_columns.items():
            if col not in real_columns:
                missing_columns.append(col)
            elif real_columns[col] != expected_type:
                print(f"   ⚠️ Tipo diverso: {col} -> {real_columns[col]} (atteso: {expected_type})")
        
        for col in real_columns:
            if col not in expected_columns:
                extra_columns.append(col)
        
        if missing_columns:
            print(f"   ❌ Colonne mancanti: {missing_columns}")
        if extra_columns:
            print(f"   ℹ️ Colonne extra: {extra_columns}")
        
        # 2. Analizza fiscal_ledger
        print("\n2️⃣ Analisi fiscal_ledger")
        
        ledger_schema = conn.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'fiscal_ledger'
            ORDER BY ordinal_position
        """).fetchall()
        
        print("   Schema reale:")
        for col, dtype in ledger_schema:
            print(f"      {col}: {dtype}")
        
        # Schema atteso da DD-6.1
        expected_ledger = {
            'id': 'BIGINT',
            'run_id': 'VARCHAR',
            'date': 'DATE',
            'type': 'VARCHAR',
            'symbol': 'VARCHAR',
            'qty': 'DOUBLE',
            'price': 'DOUBLE',
            'price_eur': 'DOUBLE',
            'exchange_rate_used': 'DOUBLE',
            'cash_delta_eur': 'DOUBLE',     # MANCANTE
            'pmc_eur': 'DOUBLE',            # MANCANTE
            'realized_pnl_eur': 'DOUBLE',   # MANCANTE
            'tax_paid_eur': 'DOUBLE',        # MANCANTE (c'è tax_paid)
            'tax_category_snapshot': 'VARCHAR', # MANCANTE
            'created_at': 'TIMESTAMP',
            'last_updated': 'TIMESTAMP'
        }
        
        real_ledger = {col: dtype for col, dtype in ledger_schema}
        
        missing_ledger = []
        for col, expected_type in expected_ledger.items():
            if col not in real_ledger:
                missing_ledger.append(col)
        
        if missing_ledger:
            print(f"   ❌ Colonne mancanti: {missing_ledger}")
        
        # Controlla uso colonne in script
        print("\n3️⃣ Verifica uso colonne in script")
        
        # Controlla se script usano colonne mancanti
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core')
        
        problematic_usages = []
        
        for script_file in ['update_ledger.py', 'sanity_check.py', 'backtest_runner.py']:
            script_path = os.path.join(scripts_dir, script_file)
            if os.path.exists(script_path):
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Controlla uso colonne che non esistono
                if 'cash_delta_eur' in content and 'cash_delta_eur' in missing_ledger:
                    problematic_usages.append(f"{script_file}: usa cash_delta_eur (mancante)")
                if 'pmc_eur' in content and 'pmc_eur' in missing_ledger:
                    problematic_usages.append(f"{script_file}: usa pmc_eur (mancante)")
                if 'realized_pnl_eur' in content and 'realized_pnl_eur' in missing_ledger:
                    problematic_usages.append(f"{script_file}: usa realized_pnl_eur (mancante)")
        
        if problematic_usages:
            print("   ❌ Script usano colonne mancanti:")
            for usage in problematic_usages:
                print(f"      {usage}")
        else:
            print("   ✅ Script coerenti con schema reale")
        
        # 4. Analizza TODOLIST optimism
        print("\n4️⃣ Analisi TODOLIST optimism")
        
        # Leggi TODOLIST
        todolist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '002 v10 - TODOLIST.md')
        with open(todolist_path, 'r', encoding='utf-8') as f:
            todolist_content = f.read()
        
        # Controlla dichiarazioni
        issues = []
        
        if 'PRODUCTION READY' in todolist_content:
            if missing_columns or missing_ledger:
                issues.append("Dichiara PRODUCTION READY ma ha schema drift")
        
        if '12/13 scripts functional' in todolist_content:
            # Verifica se ci sono script con problemi
            placeholder_scripts = []
            for script_file in os.listdir(scripts_dir):
                if script_file.endswith('.py'):
                    script_path = os.path.join(scripts_dir, script_file)
                    with open(script_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if '# TODO' in content or '# PLACEHOLDER' in content:
                        placeholder_scripts.append(script_file)
            
            if placeholder_scripts:
                issues.append(f"Dichiara 12/13 functional ma ci sono placeholder: {placeholder_scripts}")
        
        # Controlla bug logici noti
        if 'stress test' in todolist_content.lower():
            # Verifica se stress test ha bug invertito
            stress_path = os.path.join(scripts_dir, 'stress_test.py')
            if os.path.exists(stress_path):
                with open(stress_path, 'r', encoding='utf-8') as f:
                    stress_content = f.read()
                if 'risk_assessment' in stress_content.lower():
                    issues.append("Stress test ha risk assessment invertito (noto)")
        
        if issues:
            print("   ❌ TODOLIST troppo optimistic:")
            for issue in issues:
                print(f"      {issue}")
        else:
            print("   ✅ TODOLIST allineata alla realtà")
        
        # 5. Riassunto drift
        print("\n5️⃣ Riassunto Schema Drift")
        
        total_issues = len(missing_columns) + len(missing_ledger) + len(problematic_usages) + len(issues)
        
        if total_issues == 0:
            print("   ✅ Nessun drift rilevato")
        else:
            print(f"   ❌ {total_issues} problemi di drift rilevati:")
            print(f"      - Colonne market_data mancanti: {len(missing_columns)}")
            print(f"      - Colonne fiscal_ledger mancanti: {len(missing_ledger)}")
            print(f"      - Script incoerenti: {len(problematic_usages)}")
            print(f"      - TODOLIST optimism: {len(issues)}")
        
        return total_issues == 0
        
    except Exception as e:
        print(f"❌ Errore durante analisi: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = analyze_schema_drift()
    sys.exit(0 if success else 1)
