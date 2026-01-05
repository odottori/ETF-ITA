#!/usr/bin/env python3
"""
DETAILED Schema Drift Analysis - ETF Italia Project v10
Analisi approfondita delle discrepanze tra canonici e implementazione
"""

import sys
import os
import duckdb
import json
import re
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_detailed_schema_drift():
    """Analisi dettagliata drift con focus su implementazione vs documentazione"""
    
    print("🔍 DETAILED SCHEMA DRIFT ANALYSIS - ETF Italia Project v10")
    print("=" * 70)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Analisi approfondita market_data
        print("\n1️⃣ ANALISI APPROFONDITA market_data")
        print("-" * 50)
        
        # Schema reale completo
        real_schema = conn.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'market_data'
            ORDER BY ordinal_position
        """).fetchall()
        
        print("   Schema REALE (setup_db.py):")
        for col, dtype, nullable, default in real_schema:
            nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {default}" if default else ""
            print(f"      {col:15} {dtype:10} {nullable_str:8}{default_str}")
        
        # Schema atteso da DATADICTIONARY DD-2.1
        print("\n   Schema ATTESO (DATADICTIONARY DD-2.1):")
        expected_dd = {
            'symbol': {'type': 'VARCHAR', 'nullable': 'NO', 'note': 'PK (composita)'},
            'date': {'type': 'DATE', 'nullable': 'NO', 'note': 'PK (composita)'},
            'close': {'type': 'DOUBLE', 'nullable': 'NO', 'note': 'prezzo raw (ledger valuation)'},
            'adj_close': {'type': 'DOUBLE', 'nullable': 'NO', 'note': 'prezzo adjusted (signals/returns)'},
            'volume': {'type': 'BIGINT', 'nullable': 'NO', 'note': '>= 0'},
            'currency': {'type': 'VARCHAR', 'nullable': 'YES', 'note': 'es. EUR (baseline)'},
            'provider': {'type': 'VARCHAR', 'nullable': 'YES', 'note': 'es. YF, TIINGO'},
            'created_at': {'type': 'TIMESTAMP', 'nullable': 'NO', 'note': 'default now()'},
            'last_updated': {'type': 'TIMESTAMP', 'nullable': 'NO', 'note': 'default now()'}
        }
        
        for col, specs in expected_dd.items():
            print(f"      {col:15} {specs['type']:10} {specs['nullable']:8} # {specs['note']}")
        
        # Analisi discrepanze
        print("\n   ANALISI DISCREPANZE:")
        real_columns = {col: dtype for col, dtype, _, _ in real_schema}
        
        missing_critical = []
        missing_optional = []
        type_mismatches = []
        extra_columns = []
        
        for col, specs in expected_dd.items():
            if col not in real_columns:
                if specs['nullable'] == 'NO':
                    missing_critical.append(col)
                else:
                    missing_optional.append(col)
            elif real_columns[col] != specs['type']:
                type_mismatches.append((col, real_columns[col], specs['type']))
        
        for col in real_columns:
            if col not in expected_dd:
                extra_columns.append(col)
        
        if missing_critical:
            print(f"   ❌ Colonne CRITICHE mancanti: {missing_critical}")
        if missing_optional:
            print(f"   ⚠️ Colonne opzionali mancanti: {missing_optional}")
        if type_mismatches:
            for col, real, expected in type_mismatches:
                print(f"   ⚠️ Tipo diverso: {col} -> {real} (atteso: {expected})")
        if extra_columns:
            print(f"   ℹ️ Colonne extra (non in DD): {extra_columns}")
        
        # 2. Analisi approfondita fiscal_ledger
        print("\n2️⃣ ANALISI APPROFONDITA fiscal_ledger")
        print("-" * 50)
        
        ledger_schema = conn.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'fiscal_ledger'
            ORDER BY ordinal_position
        """).fetchall()
        
        print("   Schema REALE (setup_db.py):")
        for col, dtype, nullable, default in ledger_schema:
            nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {default}" if default else ""
            print(f"      {col:20} {dtype:10} {nullable_str:8}{default_str}")
        
        # Schema atteso da DATADICTIONARY DD-6.1
        print("\n   Schema ATTESO (DATADICTIONARY DD-6.1):")
        expected_ledger = {
            'id': {'type': 'BIGINT', 'nullable': 'NO', 'note': 'PK'},
            'run_id': {'type': 'VARCHAR', 'nullable': 'YES', 'note': 'link run'},
            'date': {'type': 'DATE', 'nullable': 'NO', 'note': 'data operazione (EOD model)'},
            'type': {'type': 'VARCHAR', 'nullable': 'NO', 'note': 'BUY/SELL/INTEREST/(DIVIDEND opz.)'},
            'symbol': {'type': 'VARCHAR', 'nullable': 'NO', 'note': ''},
            'qty': {'type': 'DOUBLE', 'nullable': 'NO', 'note': 'quote'},
            'price': {'type': 'DOUBLE', 'nullable': 'NO', 'note': 'prezzo unitario (valuta strumento)'},
            'price_eur': {'type': 'DOUBLE', 'nullable': 'YES', 'note': 'controvalore EUR (se FX)'},
            'exchange_rate_used': {'type': 'DOUBLE', 'nullable': 'YES', 'note': 'null nel baseline'},
            'cash_delta_eur': {'type': 'DOUBLE', 'nullable': 'YES', 'note': 'variazione cash in EUR'},
            'pmc_eur': {'type': 'DOUBLE', 'nullable': 'YES', 'note': 'PMC in EUR'},
            'realized_pnl_eur': {'type': 'DOUBLE', 'nullable': 'YES', 'note': 'su SELL'},
            'tax_paid_eur': {'type': 'DOUBLE', 'nullable': 'YES', 'note': 'imposta pagata'},
            'tax_category_snapshot': {'type': 'VARCHAR', 'nullable': 'YES', 'note': 'copia da registry'},
            'created_at': {'type': 'TIMESTAMP', 'nullable': 'NO', 'note': ''},
            'last_updated': {'type': 'TIMESTAMP', 'nullable': 'NO', 'note': ''}
        }
        
        for col, specs in expected_ledger.items():
            print(f"      {col:20} {specs['type']:10} {specs['nullable']:8} # {specs['note']}")
        
        # Analisi discrepanze fiscal_ledger
        print("\n   ANALISI DISCREPANZE:")
        real_ledger = {col: dtype for col, dtype, _, _ in ledger_schema}
        
        missing_ledger_critical = []
        missing_ledger_optional = []
        ledger_type_mismatches = []
        ledger_extra_columns = []
        
        for col, specs in expected_ledger.items():
            if col not in real_ledger:
                if specs['nullable'] == 'NO':
                    missing_ledger_critical.append(col)
                else:
                    missing_ledger_optional.append(col)
            elif real_ledger[col] != specs['type']:
                ledger_type_mismatches.append((col, real_ledger[col], specs['type']))
        
        for col in real_ledger:
            if col not in expected_ledger:
                ledger_extra_columns.append(col)
        
        if missing_ledger_critical:
            print(f"   ❌ Colonne CRITICHE mancanti: {missing_ledger_critical}")
        if missing_ledger_optional:
            print(f"   ⚠️ Colonne opzionali mancanti: {missing_ledger_optional}")
        if ledger_type_mismatches:
            for col, real, expected in ledger_type_mismatches:
                print(f"   ⚠️ Tipo diverso: {col} -> {real} (atteso: {expected})")
        if ledger_extra_columns:
            print(f"   ℹ️ Colonne extra (non in DD): {ledger_extra_columns}")
        
        # 3. Analisi implementazione reale vs script
        print("\n3️⃣ ANALISI IMPLEMENTAZIONE REALE VS SCRIPT")
        print("-" * 50)
        
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core')
        
        # Verifica uso colonne che esistono vs quelle che dovrebbero esistere
        print("   Verifica coerenza script con schema REALE:")
        
        script_issues = []
        script_consistency = []
        
        for script_file in ['update_ledger.py', 'sanity_check.py', 'backtest_runner.py', 'strategy_engine.py']:
            script_path = os.path.join(scripts_dir, script_file)
            if os.path.exists(script_path):
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Colonne usate nello script
                used_columns = set()
                
                # Pattern matching per colonne SQL
                sql_patterns = [
                    r'SELECT\s+.*?(\w+)\s+FROM',
                    r'WHERE\s+(\w+)\s*=',
                    r'INSERT.*?\((.*?)\)',
                    r'UPDATE.*?SET\s+(\w+)\s*=',
                    r'(\w+)\s+AS\s+\w+'
                ]
                
                for pattern in sql_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                    for match in matches:
                        if isinstance(match, tuple):
                            used_columns.update(match)
                        else:
                            used_columns.add(match)
                
                # Verifica se le colonne usate esistono nel schema reale
                missing_in_real = []
                for col in used_columns:
                    if col in ['symbol', 'date', 'type', 'qty', 'price', 'fees', 'tax_paid', 'pmc_snapshot', 
                              'trade_currency', 'exchange_rate_used', 'price_eur', 'run_id', 'created_at',
                              'adj_close', 'close', 'high', 'low', 'volume', 'source']:
                        continue  # Colonne che esistono
                    elif col in ['cash_delta_eur', 'pmc_eur', 'realized_pnl_eur', 'tax_paid_eur', 
                                'tax_category_snapshot', 'last_updated', 'currency', 'provider']:
                        missing_in_real.append(col)
                
                if missing_in_real:
                    script_issues.append(f"{script_file}: usa colonne mancanti {missing_in_real}")
                else:
                    script_consistency.append(f"{script_file}: coerente con schema reale")
        
        if script_consistency:
            print("   ✅ Script coerenti con schema reale:")
            for consistency in script_consistency:
                print(f"      {consistency}")
        
        if script_issues:
            print("   ❌ Script con problemi:")
            for issue in script_issues:
                print(f"      {issue}")
        
        # 4. Analisi DIPF vs implementazione
        print("\n4️⃣ ANALISI DIPF VS IMPLEMENTAZIONE")
        print("-" * 50)
        
        # Leggi DIPF
        dipf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '002 v10 - DIPF ETF-ITA prj.md')
        with open(dipf_path, 'r', encoding='utf-8') as f:
            dipf_content = f.read()
        
        print("   Verifica allineamento DIPF:")
        
        # Controlla se DIPF menziona elementi implementati
        dipf_checks = []
        
        if 'market_data' in dipf_content:
            if 'currency' in dipf_content.lower():
                dipf_checks.append("DIPF menziona currency in market_data")
            if 'provider' in dipf_content.lower():
                dipf_checks.append("DIPF menziona provider in market_data")
        
        if 'fiscal_ledger' in dipf_content:
            if 'cash_delta' in dipf_content.lower():
                dipf_checks.append("DIPF menziona cash_delta in fiscal_ledger")
            if 'pmc_eur' in dipf_content.lower():
                dipf_checks.append("DIPF menziona pmc_eur in fiscal_ledger")
        
        if dipf_checks:
            print("   ℹ️ DIPF menziona elementi non implementati:")
            for check in dipf_checks:
                print(f"      {check}")
        else:
            print("   ✅ DIPF non menziona esplicitamente elementi mancanti")
        
        # 5. Analisi impatto reale
        print("\n5️⃣ ANALISI IMPATTO REALE")
        print("-" * 50)
        
        impact_analysis = []
        
        # Impatto su market_data
        if missing_critical or missing_optional:
            impact_analysis.append({
                'area': 'market_data',
                'severity': 'HIGH' if missing_critical else 'MEDIUM',
                'missing': missing_critical + missing_optional,
                'impact': 'Mancanza metadata per audit e multi-currency support'
            })
        
        # Impatto su fiscal_ledger
        if missing_ledger_critical or missing_ledger_optional:
            impact_analysis.append({
                'area': 'fiscal_ledger',
                'severity': 'HIGH' if missing_ledger_critical else 'MEDIUM',
                'missing': missing_ledger_critical + missing_ledger_optional,
                'impact': 'Limitazioni in reporting fiscale e tracking P&L EUR'
            })
        
        # Impatto su script
        if script_issues:
            impact_analysis.append({
                'area': 'script_coherence',
                'severity': 'MEDIUM',
                'missing': [issue.split(': usa colonne')[1] for issue in script_issues],
                'impact': 'Potenziali runtime errors o logiche incomplete'
            })
        
        print("   Analisi impatto:")
        for analysis in impact_analysis:
            severity_emoji = "🔴" if analysis['severity'] == 'HIGH' else "🟡"
            print(f"   {severity_emoji} {analysis['area']}: {analysis['impact']}")
            if analysis['missing']:
                print(f"      Mancanti: {analysis['missing']}")
        
        # 6. Raccomandazioni specifiche
        print("\n6️⃣ RACCOMANDAZIONI SPECIFICHE")
        print("-" * 50)
        
        recommendations = []
        
        if missing_critical:
            recommendations.append("AGGIORNARE setup_db.py per includere colonne critiche mancanti")
        
        if missing_optional:
            recommendations.append("Valutare se aggiungere colonne opzionali per completezza")
        
        if ledger_extra_columns:
            recommendations.append("Aggiornare DATADICTIONARY per riflettere colonne extra implementate")
        
        if script_issues:
            recommendations.append("Correggere script per usare solo colonne esistenti o implementare colonne mancanti")
        
        recommendations.append("Eseguire migration script per allineare schema esistente")
        recommendations.append("Aggiornare test suite per verificare coerenza schema")
        
        print("   Raccomandazioni:")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
        
        # 7. Score finale
        print("\n7️⃣ SCORE FINALE ALLINEAMENTO")
        print("-" * 50)
        
        total_expected = len(expected_dd) + len(expected_ledger)
        total_implemented = len(real_columns) + len(real_ledger)
        total_missing = len(missing_critical + missing_optional + missing_ledger_critical + missing_ledger_optional)
        
        alignment_score = (total_implemented / total_expected) * 100 if total_expected > 0 else 0
        
        print(f"   Coloni attese (DD): {total_expected}")
        print(f"   Colonne implementate: {total_implemented}")
        print(f"   Colonne mancanti: {total_missing}")
        print(f"   Score allineamento: {alignment_score:.1f}%")
        
        if alignment_score >= 90:
            status = "🟢 ECCLENTE"
        elif alignment_score >= 75:
            status = "🟡 BUONO"
        else:
            status = "🔴 CRITICO"
        
        print(f"   Status: {status}")
        
        return alignment_score >= 75
        
    except Exception as e:
        print(f"❌ Errore durante analisi dettagliata: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = analyze_detailed_schema_drift()
    sys.exit(0 if success else 1)
