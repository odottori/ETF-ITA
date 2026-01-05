#!/usr/bin/env python3
"""
Test di Conformità - ETF Italia Project v10
Verifica che tutti i componenti siano conformi ai canonici
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_conformity():
    """Esegue tutti i test di conformità"""
    
    tests_passed = 0
    tests_total = 0
    
    print("🧪 TEST DI CONFORMITÀ - ETF Italia Project v10")
    print("=" * 50)
    
    # Test 1: Struttura cartelle
    print("\n📁 Test 1: Struttura cartelle")
    tests_total += 1
    required_dirs = ['config', 'data', 'scripts', 'data/backup', 'data/reports']
    missing_dirs = []
    
    for dir_path in required_dirs:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), dir_path)
        if not os.path.exists(full_path):
            missing_dirs.append(dir_path)
    
    if not missing_dirs:
        print("✅ Tutte le cartelle richieste esistono")
        tests_passed += 1
    else:
        print(f"❌ Mancano cartelle: {missing_dirs}")
    
    # Test 2: File di configurazione
    print("\n⚙️ Test 2: File configurazione")
    tests_total += 1
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Verifica struttura minima
            required_keys = ['settings', 'universe', 'risk_management', 'fiscal']
            if all(key in config for key in required_keys):
                print("✅ File configurazione valido e completo")
                tests_passed += 1
            else:
                print(f"❌ Chiavi mancanti: {[k for k in required_keys if k not in config]}")
        except Exception as e:
            print(f"❌ Errore lettura config: {e}")
    else:
        print("❌ File etf_universe.json non trovato")
    
    # Test 3: Database DuckDB
    print("\n🗄️ Test 3: Database DuckDB")
    tests_total += 1
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    if os.path.exists(db_path):
        try:
            conn = duckdb.connect(db_path)
            
            # Verifica tabelle richieste
            required_tables = [
                'market_data', 'staging_data', 'fiscal_ledger', 'ingestion_audit',
                'trading_calendar', 'corporate_actions', 'trade_journal', 'tax_loss_carryforward'
            ]
            
            tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            existing_tables = [row[0] for row in conn.execute(tables_query).fetchall()]
            
            missing_tables = [t for t in required_tables if t not in existing_tables]
            
            if not missing_tables:
                print("✅ Tutte le tabelle richieste esistono")
                
                # Verifica deposito iniziale
                deposit_check = conn.execute("""
                    SELECT COUNT(*) FROM fiscal_ledger 
                    WHERE type = 'DEPOSIT' AND symbol = 'CASH'
                """).fetchone()[0]
                
                if deposit_check > 0:
                    print("✅ Deposito iniziale presente nel ledger")
                    tests_passed += 1
                else:
                    print("❌ Deposito iniziale mancante nel ledger")
            else:
                print(f"❌ Tabelle mancanti: {missing_tables}")
            
            # Verifica viste
            required_views = ['risk_metrics', 'portfolio_summary']
            views_query = "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
            existing_views = [row[0] for row in conn.execute(views_query).fetchall()]
            missing_views = [v for v in required_views if v not in existing_views]
            
            if not missing_views:
                print("✅ Viste analytics presenti")
            else:
                print(f"⚠️ Viste mancanti: {missing_views}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Errore database: {e}")
    else:
        print("❌ Database DuckDB non trovato")
    
    # Test 4: Script setup_db.py
    print("\n🔧 Test 4: Script setup_db.py")
    tests_total += 1
    setup_script = os.path.join(os.path.dirname(__file__), 'setup_db.py')
    
    if os.path.exists(setup_script):
        try:
            with open(setup_script, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verifica funzioni chiave
            required_functions = ['setup_database', 'CREATE TABLE', 'market_data', 'fiscal_ledger']
            if all(func in content for func in required_functions):
                print("✅ Script setup_db.py completo")
                tests_passed += 1
            else:
                print("❌ Script setup_db.py incompleto")
        except Exception as e:
            print(f"❌ Errore lettura script: {e}")
    else:
        print("❌ Script setup_db.py non trovato")
    
    # Test 5: Librerie Python
    print("\n📚 Test 5: Librerie Python")
    tests_total += 1
    required_libs = ['duckdb', 'pandas', 'yfinance', 'plotly']
    missing_libs = []
    
    for lib in required_libs:
        try:
            __import__(lib)
        except ImportError:
            missing_libs.append(lib)
    
    if not missing_libs:
        print("✅ Tutte le librerie richieste installate")
        tests_passed += 1
    else:
        print(f"❌ Librerie mancanti: {missing_libs}")
    
    # Test 6: Git repository
    print("\n🔀 Test 6: Git repository")
    tests_total += 1
    git_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.git')
    
    if os.path.exists(git_dir):
        print("✅ Repository Git inizializzato")
        tests_passed += 1
    else:
        print("❌ Repository Git non inizializzato")
    
    # Test 7: Canonici aggiornati
    print("\n📋 Test 7: File canonici")
    tests_total += 1
    canonical_files = [
        '002 v10 - README.md',
        '002 v10 - DIPF ETF-ITA prj.md', 
        '002 v10 - DATADICTIONARY.md',
        '002 v10 - TODOLIST.md'
    ]
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    missing_canonicals = []
    
    for file_name in canonical_files:
        file_path = os.path.join(project_root, file_name)
        if not os.path.exists(file_path):
            missing_canonicals.append(file_name)
    
    if not missing_canonicals:
        print("✅ Tutti i file canonici presenti")
        tests_passed += 1
    else:
        print(f"❌ Canonici mancanti: {missing_canonicals}")
    
    # Risultato finale
    print("\n" + "=" * 50)
    print(f"📊 RISULTATO: {tests_passed}/{tests_total} test superati")
    
    if tests_passed == tests_total:
        print("🎉 TUTTI I TEST DI CONFORMITÀ SUPERATI!")
        print("✅ Il sistema è pronto per procedere con lo sviluppo")
        return True
    else:
        print(f"⚠️ {tests_total - tests_passed} test falliti - verificare i problemi")
        return False

if __name__ == "__main__":
    success = test_conformity()
    sys.exit(0 if success else 1)
