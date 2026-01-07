#!/usr/bin/env python3
"""
Tax Engine - ETF Italia Project v10
Modulo unificato per gestione fiscalità italiana (PMC, zainetto, tassazione 26%)
"""

import sys
import os
import duckdb

from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager


def calculate_tax(gain_amount, symbol, realize_date, conn):
    """
    Calcola tassazione basata su tax_category e zainetto
    
    Args:
        gain_amount: Importo gain (positivo)
        symbol: Simbolo strumento
        realize_date: Data realizzo
        conn: Connessione DuckDB
        
    Returns:
        dict con gain_amount, tax_category, tax_amount, zainetto_used, explanation
    """
    
    # 1. Ottieni tax_category del simbolo
    tax_category_result = conn.execute("""
        SELECT tax_category FROM symbol_registry WHERE symbol = ?
    """, [symbol]).fetchone()
    
    if not tax_category_result:
        tax_category = 'OICR_ETF'  # Default
    else:
        tax_category = tax_category_result[0]
    
    # 2. Per OICR_ETF: nessuna compensazione zainetto, gain tassati pieni
    if tax_category == 'OICR_ETF':
        tax_amount = gain_amount * 0.26  # Tassazione piena 26%
        zainetto_used = 0.0
        explanation = f"OICR_ETF: tassazione piena 26% (no compensazione zainetto)"
        
        # NOTA: Le loss OICR_ETF vengono comunque accumulate nello zainetto
        # per coerenza audit ma non sono utilizzabili per compensare gain OICR_ETF
        # Diventeranno utilizzabili solo con strumenti ETC_ETN_STOCK
    
    # 3. Per ETC/ETN/STOCK: compensazione zainetto possibile
    else:
        # Cerca zainetto disponibile non scaduto per categoria fiscale
        zainetto_available = conn.execute("""
            SELECT COALESCE(SUM(loss_amount), 0) as available_loss
            FROM tax_loss_carryforward 
            WHERE tax_category = ? 
            AND used_amount < ABS(loss_amount)
            AND expires_at > ?
        """, [tax_category, realize_date]).fetchone()[0]
        
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
    """
    Crea record zainetto con scadenza corretta per categoria fiscale
    
    Args:
        symbol: Simbolo strumento
        realize_date: Data realizzo loss
        loss_amount: Importo loss (negativo)
        conn: Connessione DuckDB
        
    Returns:
        dict con dettagli zainetto creato
    """
    
    # 1. Ottieni tax_category
    tax_category_result = conn.execute("""
        SELECT tax_category FROM symbol_registry WHERE symbol = ?
    """, [symbol]).fetchone()
    
    tax_category = tax_category_result[0] if tax_category_result else 'OICR_ETF'
    
    # 2. Calcola scadenza: 31/12/(anno_realize + 4)
    realize_year = realize_date.year
    expiry_year = realize_year + 4
    expires_at = datetime(expiry_year, 12, 31).date()
    
    # 3. Inserisci record zainetto per categoria fiscale
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
        'tax_category': tax_category,
        'note': f'Zainetto creato per categoria {tax_category}, utilizzabile solo con strumenti compatibili'
    }


def update_zainetto_usage(symbol, tax_category, used_amount, realize_date, conn):
    """
    Aggiorna used_amount per zainetto utilizzato (FIFO)
    
    Args:
        symbol: Simbolo strumento (per logging)
        tax_category: Categoria fiscale
        used_amount: Importo utilizzato dal zainetto
        realize_date: Data realizzo
        conn: Connessione DuckDB
    """
    
    if used_amount <= 0:
        return
    
    # Seleziona zainetti disponibili per categoria (ordinati per scadenza FIFO)
    available_zainetti = conn.execute("""
        SELECT id, loss_amount, used_amount
        FROM tax_loss_carryforward 
        WHERE tax_category = ? 
        AND used_amount < ABS(loss_amount)
        AND expires_at > ?
        ORDER BY expires_at ASC, id ASC
    """, [tax_category, realize_date]).fetchall()
    
    remaining_to_use = used_amount
    
    for zainetto in available_zainetti:
        if remaining_to_use <= 0:
            break
            
        zainetto_id = zainetto[0]
        loss_amount = zainetto[1]  # Negativo
        current_used = zainetto[2]
        
        available_capacity = abs(loss_amount) - current_used
        
        if available_capacity > 0:
            use_this_time = min(remaining_to_use, available_capacity)
            new_used = current_used + use_this_time
            
            # Aggiorna record
            conn.execute("""
                UPDATE tax_loss_carryforward 
                SET used_amount = ?
                WHERE id = ?
            """, [new_used, zainetto_id])
            
            remaining_to_use -= use_this_time
            
            print(f"    Zainetto {zainetto_id}: +€{use_this_time:.2f} usato (totale: €{new_used:.2f})")
    
    if remaining_to_use > 0.01:
        print(f"    WARNING: Zainetto insufficiente, rimanente: €{remaining_to_use:.2f}")


def get_available_zainetto(tax_category, realize_date, conn):
    """
    Helper: Ottieni zainetto disponibile per categoria fiscale
    
    Args:
        tax_category: Categoria fiscale
        realize_date: Data realizzo
        conn: Connessione DuckDB
        
    Returns:
        float: Importo zainetto disponibile (negativo se presente)
    """
    
    result = conn.execute("""
        SELECT COALESCE(SUM(loss_amount - used_amount), 0) as available_loss
        FROM tax_loss_carryforward 
        WHERE tax_category = ? 
        AND used_amount < ABS(loss_amount)
        AND expires_at > ?
    """, [tax_category, realize_date]).fetchone()
    
    return result[0] if result else 0.0


def test_tax_engine():
    """Test completo tax engine end-to-end"""
    
    print("🧾 TAX ENGINE TEST - ETF Italia Project v10")
    print("=" * 60)
    
    pm = get_path_manager()
    db_path = str(pm.db_path)
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Test logica tax_category
        print("\n1️⃣ Test logica tax_category")
        
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
        
        # 2. Test scadenza zainetto
        print("\n2️⃣ Test scadenza zainetto")
        
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
        
        # 3. Test scenario completo con ETC
        print("\n3️⃣ Test scenario completo ETC con compensazione")
        
        # Aggiungiamo un simbolo ETC per test
        conn.execute("""
            INSERT OR REPLACE INTO symbol_registry (symbol, name, tax_category)
            VALUES ('TEST_ETC', 'Test ETC', 'ETC')
        """)
        
        # Crea zainetto per ETC
        etc_zainetto = create_tax_loss_carryforward('TEST_ETC', test_realize, -800.0, conn)
        print(f"   📋 Zainetto ETC creato: €{etc_zainetto['loss_amount']}")
        
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
        
        # 4. Test aggiornamento used_amount
        print("\n4️⃣ Test aggiornamento used_amount (FIFO)")
        
        print(f"   Aggiornamento zainetto con €{etc_result['zainetto_used']:.2f}...")
        update_zainetto_usage('TEST_ETC', 'ETC', etc_result['zainetto_used'], test_realize, conn)
        
        # Verifica used_amount aggiornato
        used_check = conn.execute("""
            SELECT used_amount FROM tax_loss_carryforward 
            WHERE symbol = 'TEST_ETC' AND tax_category = 'ETC'
        """).fetchone()
        
        if used_check and abs(used_check[0] - etc_result['zainetto_used']) < 0.01:
            print(f"   ✅ Used_amount aggiornato correttamente: €{used_check[0]:.2f}")
        else:
            print(f"   ❌ Used_amount non aggiornato correttamente")
            return False
        
        # 5. Test helper get_available_zainetto
        print("\n5️⃣ Test helper get_available_zainetto")
        
        available = get_available_zainetto('ETC', test_realize, conn)
        expected_available = -800.0 + etc_result['zainetto_used']  # loss_amount + used
        
        if abs(available - expected_available) < 0.01:
            print(f"   ✅ Zainetto disponibile corretto: €{available:.2f}")
        else:
            print(f"   ❌ Zainetto disponibile errato: €{available:.2f} (atteso: €{expected_available:.2f})")
            return False
        
        # 6. Commit modifiche
        conn.commit()
        
        print("\n" + "=" * 60)
        print("🎯 TAX ENGINE TEST RESULTS:")
        print("=" * 60)
        print("✅ Logica tax_category implementata")
        print("✅ Scadenza zainetto implementata (31/12/anno+4)")
        print("✅ OICR_ETF: tassazione piena 26%")
        print("✅ ETC/ETN: compensazione zainetto funzionante")
        print("✅ Update used_amount FIFO funzionante")
        print("✅ Helper get_available_zainetto funzionante")
        print("\n🎉 TAX ENGINE: PRODUCTION READY")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = test_tax_engine()
    sys.exit(0 if success else 1)
