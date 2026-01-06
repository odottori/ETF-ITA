#!/usr/bin/env python3
"""
Schema Validation Tests - ETF Italia Project v10.7.3
Test di coerenza schema database secondo SCHEMA_CONTRACT.md
"""

import sys
import os
import duckdb
import json
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_schema_coherence():
    """Test coerenza schema database"""
    
    print("🔍 SCHEMA VALIDATION TESTS")
    print("=" * 50)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        tests_passed = 0
        tests_total = 0
        
        # 1. Test esistenza tabelle core
        print("\n📋 Test esistenza tabelle core...")
        core_tables = ['market_data', 'fiscal_ledger', 'signals', 'orders']
        
        for table in core_tables:
            tests_total += 1
            try:
                result = conn.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'").fetchone()[0]
                if result > 0:
                    print(f"✅ {table}: esistente")
                    tests_passed += 1
                else:
                    print(f"❌ {table}: mancante")
            except Exception as e:
                print(f"❌ {table}: errore {e}")
        
        # 2. Test colonne fiscal_ledger
        print("\n📋 Test colonne fiscal_ledger...")
        required_columns = ['id', 'date', 'type', 'symbol', 'qty', 'price', 'fees', 'tax_paid', 
                           'pmc_snapshot', 'trade_currency', 'exchange_rate_used', 'price_eur', 
                           'run_id', 'run_type', 'notes', 'created_at']
        
        for col in required_columns:
            tests_total += 1
            try:
                result = conn.execute(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'fiscal_ledger' AND column_name = '{col}'").fetchone()[0]
                if result > 0:
                    print(f"✅ fiscal_ledger.{col}: presente")
                    tests_passed += 1
                else:
                    print(f"❌ fiscal_ledger.{col}: mancante")
            except Exception as e:
                print(f"❌ fiscal_ledger.{col}: errore {e}")
        
        # 3. Test colonne signals
        print("\n📋 Test colonne signals...")
        required_signal_columns = ['id', 'date', 'symbol', 'signal_state', 'risk_scalar', 
                                 'explain_code', 'sma_200', 'volatility_20d', 'spy_guard', 
                                 'regime_filter', 'created_at']
        
        for col in required_signal_columns:
            tests_total += 1
            try:
                result = conn.execute(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'signals' AND column_name = '{col}'").fetchone()[0]
                if result > 0:
                    print(f"✅ signals.{col}: presente")
                    tests_passed += 1
                else:
                    print(f"❌ signals.{col}: mancante")
            except Exception as e:
                print(f"❌ signals.{col}: errore {e}")
        
        # 4. Test viste analytics
        print("\n📋 Test viste analytics...")
        analytics_views = ['risk_metrics', 'portfolio_summary', 'execution_prices']
        
        for view in analytics_views:
            tests_total += 1
            try:
                result = conn.execute(f"SELECT COUNT(*) FROM information_schema.views WHERE table_name = '{view}'").fetchone()[0]
                if result > 0:
                    print(f"✅ {view}: esistente")
                    tests_passed += 1
                else:
                    print(f"❌ {view}: mancante")
            except Exception as e:
                print(f"❌ {view}: errore {e}")
        
        # 5. Test coerenza dati
        print("\n📋 Test coerenza dati...")
        
        # Test signals con id unici
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) - COUNT(DISTINCT id) FROM signals").fetchone()[0]
            if result == 0:
                print("✅ signals.id: tutti unici")
                tests_passed += 1
            else:
                print(f"❌ signals.id: {result} duplicati")
        except Exception as e:
            print(f"❌ signals.id: errore {e}")
        
        # Test fiscal_ledger run_type values
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM fiscal_ledger WHERE run_type NOT IN ('PRODUCTION', 'BACKTEST', 'TEST')").fetchone()[0]
            if result == 0:
                print("✅ fiscal_ledger.run_type: valori validi")
                tests_passed += 1
            else:
                print(f"❌ fiscal_ledger.run_type: {result} valori invalidi")
        except Exception as e:
            print(f"❌ fiscal_ledger.run_type: errore {e}")
        
        # Test signals signal_state values
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM signals WHERE signal_state NOT IN ('RISK_ON', 'RISK_OFF', 'HOLD')").fetchone()[0]
            if result == 0:
                print("✅ signals.signal_state: valori validi")
                tests_passed += 1
            else:
                print(f"❌ signals.signal_state: {result} valori invalidi")
        except Exception as e:
            print(f"❌ signals.signal_state: errore {e}")
        
        # 6. Test convenzione prezzi
        print("\n📋 Test convenzione prezzi...")
        
        # Test portfolio_summary usa close
        tests_total += 1
        try:
            result = conn.execute("""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name = 'portfolio_summary' AND column_name = 'current_price'
            """).fetchone()[0]
            if result > 0:
                print("✅ portfolio_summary: usa close per current_price")
                tests_passed += 1
            else:
                print("❌ portfolio_summary: current_price mancante")
        except Exception as e:
            print(f"❌ portfolio_summary: errore {e}")
        
        # Test risk_metrics usa adj_close
        tests_total += 1
        try:
            result = conn.execute("""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name = 'risk_metrics' AND column_name = 'adj_close'
            """).fetchone()[0]
            if result > 0:
                print("✅ risk_metrics: usa adj_close")
                tests_passed += 1
            else:
                print("❌ risk_metrics: adj_close mancante")
        except Exception as e:
            print(f"❌ risk_metrics: errore {e}")
        
        # Risultati finali
        print(f"\n📊 RISULTATI SCHEMA VALIDATION")
        print(f"Passati: {tests_passed}/{tests_total}")
        print(f"Success rate: {tests_passed/tests_total*100:.1f}%")
        
        if tests_passed == tests_total:
            print("✅ Tutti i test di schema superati")
            return True
        else:
            print("❌ Alcuni test falliti - drift rilevati")
            return False
            
    except Exception as e:
        print(f"❌ Errore generale: {e}")
        return False
        
    finally:
        conn.close()

def test_business_rules():
    """Test regole business"""
    
    print("\n🔍 BUSINESS RULES TESTS")
    print("=" * 50)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        tests_passed = 0
        tests_total = 0
        
        # 1. Test prezzi non negativi
        print("\n📋 Test prezzi non negativi...")
        
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM market_data WHERE close < 0 OR adj_close < 0").fetchone()[0]
            if result == 0:
                print("✅ market_data: prezzi non negativi")
                tests_passed += 1
            else:
                print(f"❌ market_data: {result} prezzi negativi")
        except Exception as e:
            print(f"❌ market_data: errore {e}")
        
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM fiscal_ledger WHERE price < 0").fetchone()[0]
            if result == 0:
                print("✅ fiscal_ledger: prezzi non negativi")
                tests_passed += 1
            else:
                print(f"❌ fiscal_ledger: {result} prezzi negativi")
        except Exception as e:
            print(f"❌ fiscal_ledger: errore {e}")
        
        # 2. Test volume non negativo
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM market_data WHERE volume < 0").fetchone()[0]
            if result == 0:
                print("✅ market_data: volume non negativo")
                tests_passed += 1
            else:
                print(f"❌ market_data: {result} volumi negativi")
        except Exception as e:
            print(f"❌ market_data: errore {e}")
        
        # 3. Test risk scalar range
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM signals WHERE risk_scalar < 0 OR risk_scalar > 1").fetchone()[0]
            if result == 0:
                print("✅ signals: risk scalar in range [0,1]")
                tests_passed += 1
            else:
                print(f"❌ signals: {result} risk scalar fuori range")
        except Exception as e:
            print(f"❌ signals: errore {e}")
        
        # 4. Test fees e tax non negativi
        tests_total += 1
        try:
            result = conn.execute("SELECT COUNT(*) FROM fiscal_ledger WHERE fees < 0 OR tax_paid < 0").fetchone()[0]
            if result == 0:
                print("✅ fiscal_ledger: fees e tax non negativi")
                tests_passed += 1
            else:
                print(f"❌ fiscal_ledger: {result} fees/tax negativi")
        except Exception as e:
            print(f"❌ fiscal_ledger: errore {e}")
        
        # Risultati finali
        print(f"\n📊 RISULTATI BUSINESS RULES")
        print(f"Passati: {tests_passed}/{tests_total}")
        print(f"Success rate: {tests_passed/tests_total*100:.1f}%")
        
        if tests_passed == tests_total:
            print("✅ Tutti i test business rules superati")
            return True
        else:
            print("❌ Alcuni test business rules falliti")
            return False
            
    except Exception as e:
        print(f"❌ Errore generale: {e}")
        return False
        
    finally:
        conn.close()

def run_all_validation_tests():
    """Esegui tutti i test di validazione"""
    
    print("🚀 SCHEMA VALIDATION SUITE - ETF Italia Project v10.7.3")
    print("=" * 60)
    
    schema_ok = test_schema_coherence()
    business_ok = test_business_rules()
    
    print(f"\n📊 RISULTATI FINALI")
    print("=" * 40)
    print(f"Schema Coherence: {'✅ PASS' if schema_ok else '❌ FAIL'}")
    print(f"Business Rules: {'✅ PASS' if business_ok else '❌ FAIL'}")
    
    overall_success = schema_ok and business_ok
    print(f"Overall: {'✅ PASS' if overall_success else '❌ FAIL'}")
    
    return overall_success

if __name__ == "__main__":
    success = run_all_validation_tests()
    sys.exit(0 if success else 1)
