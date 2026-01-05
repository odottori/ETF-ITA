#!/usr/bin/env python3
"""
Tax Logic Implementation - ETF Italia Project v10
Implementa logica tax_category e scadenza zainetto
"""

import sys
import os
import duckdb
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def calculate_tax(gain_amount, symbol, realize_date, conn):
    """Calcola tassazione basata su tax_category e zainetto"""
    
    # 1. Ottieni tax_category del simbolo
    tax_category_result = conn.execute("""
        SELECT tax_category FROM symbol_registry WHERE symbol = ?
    """, [symbol]).fetchone()
    
    if not tax_category_result:
        tax_category = 'OICR_ETF'  # Default
    else:
        tax_category = tax_category_result[0]
    
    # 2. Per OICR_ETF: nessuna compensazione zainetto
    if tax_category == 'OICR_ETF':
        tax_amount = gain_amount * 0.26  # Tassazione piena 26%
        zainetto_used = 0.0
        explanation = f"OICR_ETF: tassazione piena 26% (no compensazione zainetto)"
    
    # 3. Per ETC/ETN/STOCK: compensazione zainetto possibile
    else:
        # Cerca zainetto disponibile non scaduto
        zainetto_available = conn.execute("""
            SELECT COALESCE(SUM(loss_amount), 0) as available_loss
            FROM tax_loss_carryforward 
            WHERE symbol = ? 
            AND used_amount < ABS(loss_amount)
            AND expires_at > ?
        """, [symbol, realize_date]).fetchone()[0]
        
        if zainetto_available < 0:  # C'è zainetto disponibile
            # Compensa il gain con lo zainetto
            compensable_amount = min(gain_amount, abs(zainetto_available))
            taxable_gain = gain_amount - compensable_amount
            
            tax_amount = max(0, taxable_gain) * 0.26
            zainetto_used = compensable_amount
            
            explanation = f"{tax_category}: compensato €{compensable_amount:.2f} con zainetto, tassato €{taxable_gain:.2f}"
        else:
            # Nessun zainetto disponibile
            tax_amount = gain_amount * 0.26
            zainetto_used = 0.0
            explanation = f"{tax_category}: nessun zainetto disponibile, tassazione piena"
    
    return {
        'gain_amount': gain_amount,
        'tax_category': tax_category,
        'tax_amount': tax_amount,
        'zainetto_used': zainetto_used,
        'explanation': explanation
    }

def create_tax_loss_carryforward(symbol, realize_date, loss_amount, conn):
    """Crea record zainetto con scadenza corretta"""
    
    # 1. Ottieni tax_category
    tax_category_result = conn.execute("""
        SELECT tax_category FROM symbol_registry WHERE symbol = ?
    """, [symbol]).fetchone()
    
    tax_category = tax_category_result[0] if tax_category_result else 'OICR_ETF'
    
    # 2. Calcola scadenza: 31/12/(anno_realize + 4)
    realize_year = realize_date.year
    expiry_year = realize_year + 4
    expires_at = datetime(expiry_year, 12, 31).date()
    
    # 3. Inserisci record zainetto
    next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tax_loss_carryforward").fetchone()[0]
    
    conn.execute("""
        INSERT INTO tax_loss_carryforward 
        (id, symbol, realize_date, loss_amount, used_amount, expires_at, tax_category)
        VALUES (?, ?, ?, ?, 0, ?, ?)
    """, [next_id, symbol, realize_date, loss_amount, expires_at, tax_category])
    
    return {
        'symbol': symbol,
        'realize_date': realize_date,
        'loss_amount': loss_amount,
        'expires_at': expires_at,
        'tax_category': tax_category
    }

def test_tax_logic():
    """Test completo logica tax_category e zainetto"""
    
    print("🧾 TAX LOGIC IMPLEMENTATION - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Test TL-2.1: Logica tax_category
        print("1️⃣ Test TL-2.1: Logica tax_category")
        
        # Scenario: Gain ETF + zainetto presente
        test_date = datetime(2026, 1, 5).date()
        
        # Test OICR_ETF (no compensazione)
        oicr_result = calculate_tax(500.0, 'CSSPX.MI', test_date, conn)
        print(f"   📊 OICR_ETF (CSSPX.MI):")
        print(f"      Gain: €{oicr_result['gain_amount']}")
        print(f"      Tax: €{oicr_result['tax_amount']:.2f}")
        print(f"      Zainetto usato: €{oicr_result['zainetto_used']:.2f}")
        print(f"      {oicr_result['explanation']}")
        
        # Verifica: OICR_ETF deve pagare tassa piena
        expected_oicr_tax = 500.0 * 0.26  # 130
        if abs(oicr_result['tax_amount'] - expected_oicr_tax) < 0.01:
            print("   ✅ OICR_ETF: tassazione piena corretta")
        else:
            print("   ❌ OICR_ETF: tassazione errata")
            return False
        
        # 2. Test TL-2.2: Scadenza zainetto
        print("\n2️⃣ Test TL-2.2: Scadenza zainetto")
        
        # Test formula scadenza
        test_realize = datetime(2026, 1, 5).date()
        zainetto_record = create_tax_loss_carryforward('XS2L.MI', test_realize, -1000.0, conn)
        
        expected_expiry = datetime(2030, 12, 31).date()
        if zainetto_record['expires_at'] == expected_expiry:
            print(f"   ✅ Scadenza corretta: {zainetto_record['expires_at']}")
        else:
            print(f"   ❌ Scadenza errata: {zainetto_record['expires_at']} (atteso: {expected_expiry})")
            return False
        
        print(f"   📋 Zainetto creato:")
        print(f"      Simbolo: {zainetto_record['symbol']}")
        print(f"      Perdita: €{zainetto_record['loss_amount']}")
        print(f"      Realize: {zainetto_record['realize_date']}")
        print(f"      Scadenza: {zainetto_record['expires_at']}")
        print(f"      Tax Category: {zainetto_record['tax_category']}")
        
        # 3. Test scenario completo
        print("\n3️⃣ Test scenario completo")
        
        # Simula gain con zainetto disponibile per ETC/ETN
        # Aggiungiamo un simbolo ETC per test
        conn.execute("""
            INSERT OR REPLACE INTO symbol_registry (symbol, name, tax_category)
            VALUES ('TEST_ETC', 'Test ETC', 'ETC')
        """)
        
        # Crea zainetto per ETC
        etc_zainetto = create_tax_loss_carryforward('TEST_ETC', test_realize, -800.0, conn)
        
        # Calcola tassazione ETC con zainetto
        etc_result = calculate_tax(500.0, 'TEST_ETC', test_realize, conn)
        print(f"   📊 ETC (TEST_ETC):")
        print(f"      Gain: €{etc_result['gain_amount']}")
        print(f"      Tax: €{etc_result['tax_amount']:.2f}")
        print(f"      Zainetto usato: €{etc_result['zainetto_used']:.2f}")
        print(f"      {etc_result['explanation']}")
        
        # Verifica: ETC deve compensare con zainetto
        if etc_result['zainetto_used'] > 0 and etc_result['tax_amount'] < 500 * 0.26:
            print("   ✅ ETC: compensazione zainetto funzionante")
        else:
            print("   ❌ ETC: compensazione zainetto non funzionante")
            return False
        
        # 4. Commit modifiche
        conn.commit()
        
        print("\n" + "=" * 60)
        print("🎯 TAX LOGIC IMPLEMENTATION RESULTS:")
        print("=" * 60)
        print("✅ TL-2.1: Logica tax_category implementata")
        print("✅ TL-2.2: Scadenza zainetto implementata")
        print("✅ OICR_ETF: tassazione piena 26%")
        print("✅ ETC/ETN: compensazione zainetto funzionante")
        print("✅ Formula expires_at: 31/12/(anno+4)")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = test_tax_logic()
    sys.exit(0 if success else 1)
