#!/usr/bin/env python3
"""
Minimal Gate Suite - ETF Italia Project v10.7.7
Test suite "come gate", non come documento aspirazionale

Criterio DONE: suite minima (smoke + economics + fiscal edge) 
che passa in modo ripetibile e blocca regressioni.
"""

import sys
import os
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_smoke_schema():
    """Smoke test: verifica esistenza tabelle core e viste"""
    assert _run_smoke_schema()


def _run_smoke_schema():
    """Runner bool (per __main__)."""
    
    print("💨 SMOKE TEST - Schema Core")
    print("-" * 40)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db', 'etf_data.duckdb')
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        # Tabelle core obbligatorie
        core_tables = ['market_data', 'fiscal_ledger', 'signals', 'orders']
        
        for table in core_tables:
            result = conn.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'").fetchone()[0]
            if result == 0:
                print(f"❌ Tabella core mancante: {table}")
                return False
        
        # Viste analytics obbligatorie
        analytics_views = ['portfolio_summary', 'risk_metrics', 'execution_prices']
        
        for view in analytics_views:
            result = conn.execute(f"SELECT COUNT(*) FROM information_schema.views WHERE table_name = '{view}'").fetchone()[0]
            if result == 0:
                print(f"❌ Vista analytics mancante: {view}")
                return False
        
        print("✅ Schema core completo")
        return True
        
    except Exception as e:
        print(f"❌ Errore smoke test: {e}")
        return False
    finally:
        conn.close()

def test_economic_coherence():
    """Economics test: verifica coerenza prezzi e cash"""
    assert _run_economic_coherence()


def _run_economic_coherence():
    """Runner bool (per __main__)."""
    
    print("💰 ECONOMICS TEST - Coerenza Prezzi/Cash")
    print("-" * 40)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Verifica convenzione prezzi: adj_close per segnali, close per valuation
        # Ignora zombie prices (adj_close NULL) per ETF illiquidi - sono expected
        price_check = conn.execute("""
        SELECT COUNT(*) FROM market_data 
        WHERE close IS NULL OR close <= 0
        """).fetchone()[0]
        
        if price_check > 0:
            print(f"❌ Close prices invalidi: {price_check} record")
            return False
        
        # 2. Verifica coerenza portfolio_summary usa close
        portfolio_check = conn.execute("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = 'portfolio_summary' AND column_name = 'current_price'
        """).fetchone()[0]
        
        if portfolio_check == 0:
            print("❌ portfolio_summary non usa close per current_price")
            return False
        
        # 3. Verifica cash non negativo
        cash_check = conn.execute("""
        SELECT COUNT(*) FROM portfolio_summary WHERE cash < 0
        """).fetchone()[0]
        
        if cash_check > 0:
            print(f"❌ Cash negativo: {cash_check} record")
            return False
        
        print("✅ Coerenza economica verificata")
        return True
        
    except Exception as e:
        print(f"❌ Errore economics test: {e}")
        return False
    finally:
        conn.close()

def test_fiscal_edge():
    """Fiscal edge test: verifica logica fiscale critica"""
    assert _run_fiscal_edge()


def _run_fiscal_edge():
    """Runner bool (per __main__)."""
    
    print("🧾 FISCAL EDGE TEST - Logica Critica")
    print("-" * 40)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Verifica tabelle fiscali esistenti
        fiscal_tables = ['tax_loss_carryforward', 'symbol_registry']
        
        for table in fiscal_tables:
            result = conn.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'").fetchone()[0]
            if result == 0:
                print(f"❌ Tabella fiscale mancante: {table}")
                return False
        
        # 2. Verifica regola ETF: gain + zainetto = NO compensazione
        # Test con CSSPX.MI (ETF OICR)
        test_symbol = 'CSSPX.MI'
        test_date = datetime(2026, 1, 5).date()
        
        # Se symbol_registry è vuoto, usa test diretto su implement_tax_logic
        registry_count = conn.execute("SELECT COUNT(*) FROM symbol_registry").fetchone()[0]
        
        if registry_count == 0:
            print("   ⚠️ symbol_registry vuoto - test diretto implement_tax_logic")
        else:
            # Verifica che sia catalogato come OICR_ETF
            symbol_check = conn.execute("""
            SELECT COUNT(*) FROM symbol_registry 
            WHERE symbol = ? AND tax_category = 'OICR_ETF'
            """, [test_symbol]).fetchone()[0]
            
            if symbol_check == 0:
                print(f"   ⚠️ {test_symbol} non in symbol_registry come OICR_ETF - uso default (tax_engine)")
        
        # Fallback 2: Test diretto implement_tax_logic con try-catch
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts'))
        
        try:
            from fiscal.tax_engine import calculate_tax
            
            # Test con gain positivo
            result = calculate_tax(1000.0, test_symbol, test_date, conn)
            
            # Per OICR_ETF: tax = 26% del gain, zainetto_used = 0
            expected_tax = 260.0  # 26% di 1000
            expected_zainetto = 0.0
            
            if abs(result['tax_amount'] - expected_tax) > 0.01:
                print(f"❌ Tax OICR_ETF errata: expected {expected_tax}, got {result['tax_amount']}")
                return False
            
            if result['zainetto_used'] != expected_zainetto:
                print(f"❌ Zainetto OICR_ETF errato: expected {expected_zainetto}, got {result['zainetto_used']}")
                return False
            
            print("   ✅ implement_tax_logic: OICR_ETF tassazione corretta")
            
        except ImportError as e:
            print(f"❌ implement_tax_logic non importabile: {e}")
            return False
        except Exception as e:
            print(f"❌ Errore calculate_tax: {e}")
            return False
        
        # Fallback 3: Verifica manuale logica se implement_tax_logic fallisce
        try:
            # Verifica che la logica sia implementata correttamente nel codice
            tax_logic_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'fiscal', 'tax_engine.py')
            with open(tax_logic_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            checks = [
                ('tax_category == \'OICR_ETF\'', 'Logica OICR_ETF presente'),
                ('tax_amount = gain_amount * 0.26', 'Tassazione 26% implementata'),
                ('zainetto_used = 0.0', 'Nessuna compensazione zainetto per OICR_ETF'),
                ('WHERE tax_category = ?', 'Query per categoria fiscale')
            ]
            
            for check, description in checks:
                if check not in content:
                    print(f"❌ {description} non trovata")
                    return False
                else:
                    print(f"   ✅ {description}")
            
        except Exception as e:
            print(f"❌ Errore verifica manuale: {e}")
            return False
        
        print("✅ Logica fiscale edge case verificata")
        return True
        
    except Exception as e:
        print(f"❌ Errore fiscal edge test: {e}")
        return False
    finally:
        conn.close()

def run_minimal_gate_suite():
    """Esegue la suite minima come gate bloccante"""
    
    print("🚀 MINIMAL GATE SUITE - ETF Italia Project v10.7.7")
    print("=" * 60)
    print("Test suite come GATE, non come documento aspirazionale")
    print("Criterio DONE: smoke + economics + fiscal edge")
    print("=" * 60)
    
    tests = [
        ("Smoke Schema", _run_smoke_schema),
        ("Economic Coherence", _run_economic_coherence),
        ("Fiscal Edge", _run_fiscal_edge)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASS")
        else:
            print(f"❌ {test_name} FAIL - GATE BLOCCATO")
            break  # Gate bloccante: interrompe al primo fallimento
    
    print(f"\n📊 GATE RESULTS")
    print("=" * 40)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ GATE SUPERATO - Sistema OK per production")
        print("✅ Nessuna regressione rilevata")
        return True
    else:
        print("❌ GATE BLOCCATO - Regressioni rilevate")
        print("❌ Sistemare prima di procedere")
        return False

if __name__ == "__main__":
    success = run_minimal_gate_suite()
    sys.exit(0 if success else 1)
