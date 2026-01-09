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


def _has_column(conn, table: str, col: str) -> bool:
    """True se la tabella contiene la colonna (DuckDB)."""
    try:
        cols = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        return col in {c[1] for c in cols}
    except Exception:
        return False


def calculate_tax(gain_amount, symbol, realize_date, conn, run_type: str = 'PRODUCTION'):
    """Calcola tassazione basata su tax_category e zainetto.

    Invariant: costi/tasse sono informazione/penalty, non gating monetario.

    Nota robustezza: alcuni DB di test minimali non hanno la colonna run_type in
    tax_loss_carryforward; in tal caso la logica ignora il filtro per run_type.
    """

    # 1) tax_category
    tax_category_result = conn.execute(
        "SELECT tax_category FROM symbol_registry WHERE symbol = ?",
        [symbol],
    ).fetchone()

    tax_category = tax_category_result[0] if tax_category_result else 'OICR_ETF'

    # 2) OICR_ETF: no compensazione
    if tax_category == 'OICR_ETF':
        tax_amount = gain_amount * 0.26
        zainetto_used = 0.0
        explanation = 'OICR_ETF: tassazione piena 26% (no compensazione zainetto)'

        return {
            'gain_amount': gain_amount,
            'tax_category': tax_category,
            'tax_amount': float(tax_amount),
            'zainetto_used': float(zainetto_used),
            'explanation': explanation,
        }

    # 3) ETC/ETN/STOCK: compensazione zainetto possibile
    if _has_column(conn, 'tax_loss_carryforward', 'run_type'):
        zainetto_available = conn.execute(
            """
            SELECT COALESCE(SUM(loss_amount) + SUM(used_amount), 0) as available_loss
            FROM tax_loss_carryforward
            WHERE tax_category = ?
              AND COALESCE(run_type, 'PRODUCTION') = ?
              AND used_amount < ABS(loss_amount)
              AND expires_at > ?
            """,
            [tax_category, run_type, realize_date],
        ).fetchone()[0]
    else:
        zainetto_available = conn.execute(
            """
            SELECT COALESCE(SUM(loss_amount) + SUM(used_amount), 0) as available_loss
            FROM tax_loss_carryforward
            WHERE tax_category = ?
              AND used_amount < ABS(loss_amount)
              AND expires_at > ?
            """,
            [tax_category, realize_date],
        ).fetchone()[0]

    zainetto_available = float(zainetto_available or 0.0)

    if zainetto_available < 0:
        compensable_amount = min(float(gain_amount), abs(zainetto_available))
        taxable_gain = float(gain_amount) - compensable_amount
        tax_amount = max(0.0, taxable_gain) * 0.26
        return {
            'gain_amount': gain_amount,
            'tax_category': tax_category,
            'tax_amount': tax_amount,
            'zainetto_used': compensable_amount,
            'explanation': f"{tax_category}: compensato €{compensable_amount:.2f} con zainetto, tassato €{taxable_gain:.2f}",
        }

    # Nessun zainetto
    return {
        'gain_amount': gain_amount,
        'tax_category': tax_category,
        'tax_amount': float(gain_amount) * 0.26,
        'zainetto_used': 0.0,
        'explanation': f"{tax_category}: nessun zainetto disponibile, tassazione piena",
    }


def create_tax_loss_carryforward(symbol, realize_date, loss_amount, conn, run_type: str = 'PRODUCTION'):
    """Crea record zainetto con scadenza corretta per categoria fiscale.

    Nota robustezza: se la tabella non ha run_type (DB legacy/test), inserisce
    senza la colonna.
    """

    tax_category_result = conn.execute(
        "SELECT tax_category FROM symbol_registry WHERE symbol = ?",
        [symbol],
    ).fetchone()
    tax_category = tax_category_result[0] if tax_category_result else 'OICR_ETF'

    # 31/12/(anno+4)
    expires_at = datetime(realize_date.year + 4, 12, 31).date()

    next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tax_loss_carryforward").fetchone()[0]

    if _has_column(conn, 'tax_loss_carryforward', 'run_type'):
        conn.execute(
            """
            INSERT INTO tax_loss_carryforward
            (id, symbol, realize_date, loss_amount, used_amount, expires_at, tax_category, run_type)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            [next_id, symbol, realize_date, loss_amount, expires_at, tax_category, run_type],
        )
    else:
        conn.execute(
            """
            INSERT INTO tax_loss_carryforward
            (id, symbol, realize_date, loss_amount, used_amount, expires_at, tax_category)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            [next_id, symbol, realize_date, loss_amount, expires_at, tax_category],
        )

    return {
        'symbol': symbol,
        'realize_date': realize_date,
        'loss_amount': loss_amount,
        'expires_at': expires_at,
        'tax_category': tax_category,
        'note': f'Zainetto creato per categoria {tax_category}',
    }


def update_zainetto_usage(symbol, tax_category, used_amount, realize_date, conn, run_type: str = 'PRODUCTION'):
    """Aggiorna used_amount per zainetto utilizzato (FIFO).

    Nota: selezione filtrata per run_type se disponibile.
    """

    if used_amount <= 0:
        return

    if _has_column(conn, 'tax_loss_carryforward', 'run_type'):
        available_zainetti = conn.execute(
            """
            SELECT id, loss_amount, used_amount
            FROM tax_loss_carryforward
            WHERE tax_category = ?
              AND COALESCE(run_type, 'PRODUCTION') = ?
              AND used_amount < ABS(loss_amount)
              AND expires_at > ?
            ORDER BY expires_at ASC, id ASC
            """,
            [tax_category, run_type, realize_date],
        ).fetchall()
    else:
        available_zainetti = conn.execute(
            """
            SELECT id, loss_amount, used_amount
            FROM tax_loss_carryforward
            WHERE tax_category = ?
              AND used_amount < ABS(loss_amount)
              AND expires_at > ?
            ORDER BY expires_at ASC, id ASC
            """,
            [tax_category, realize_date],
        ).fetchall()

    remaining_to_use = float(used_amount)

    for zainetto_id, loss_amount, current_used in available_zainetti:
        if remaining_to_use <= 0:
            break

        loss_amount = float(loss_amount)
        current_used = float(current_used or 0.0)

        available_capacity = abs(loss_amount) - current_used
        if available_capacity <= 0:
            continue

        use_this_time = min(remaining_to_use, available_capacity)
        new_used = current_used + use_this_time

        conn.execute(
            "UPDATE tax_loss_carryforward SET used_amount = ? WHERE id = ?",
            [new_used, zainetto_id],
        )

        remaining_to_use -= use_this_time

    if remaining_to_use > 0.01:
        print(f"    WARNING: Zainetto insufficiente, rimanente: €{remaining_to_use:.2f}")


def get_available_zainetto(tax_category, realize_date, conn, run_type: str = 'PRODUCTION'):
    """Ritorna zainetto disponibile (negativo se presente).

    Disponibile = SUM(loss_amount) + SUM(used_amount)
    """

    if _has_column(conn, 'tax_loss_carryforward', 'run_type'):
        result = conn.execute(
            """
            SELECT COALESCE(SUM(loss_amount) + SUM(used_amount), 0) as available_loss
            FROM tax_loss_carryforward
            WHERE tax_category = ?
              AND COALESCE(run_type, 'PRODUCTION') = ?
              AND used_amount < ABS(loss_amount)
              AND expires_at > ?
            """,
            [tax_category, run_type, realize_date],
        ).fetchone()
    else:
        result = conn.execute(
            """
            SELECT COALESCE(SUM(loss_amount) + SUM(used_amount), 0) as available_loss
            FROM tax_loss_carryforward
            WHERE tax_category = ?
              AND used_amount < ABS(loss_amount)
              AND expires_at > ?
            """,
            [tax_category, realize_date],
        ).fetchone()

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
            INSERT OR REPLACE INTO symbol_registry (symbol, name, category, currency, tax_category)
            VALUES ('TEST_ETC', 'Test ETC', 'ETC', 'EUR', 'ETC')
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
        
        # Verifica used_amount PRIMA dell'aggiornamento
        used_before = conn.execute("""
            SELECT COALESCE(SUM(used_amount), 0) FROM tax_loss_carryforward 
            WHERE tax_category = 'ETC' AND expires_at > ?
        """, [test_realize]).fetchone()[0]
        
        print(f"   Aggiornamento zainetto con €{etc_result['zainetto_used']:.2f}...")
        update_zainetto_usage('TEST_ETC', 'ETC', etc_result['zainetto_used'], test_realize, conn)
        
        # Verifica used_amount DOPO l'aggiornamento (somma totale)
        used_after = conn.execute("""
            SELECT COALESCE(SUM(used_amount), 0) FROM tax_loss_carryforward 
            WHERE tax_category = 'ETC' AND expires_at > ?
        """, [test_realize]).fetchone()[0]
        
        used_delta = used_after - used_before
        
        if abs(used_delta - etc_result['zainetto_used']) < 0.01:
            print(f"   ✅ Used_amount aggiornato correttamente: +€{used_delta:.2f}")
        else:
            print(f"   ❌ Used_amount non aggiornato correttamente: +€{used_delta:.2f} (atteso: €{etc_result['zainetto_used']:.2f})")
            return False
        
        # 5. Test helper get_available_zainetto
        print("\n5️⃣ Test helper get_available_zainetto")
        
        # Verifica che il zainetto disponibile sia negativo (loss disponibile)
        available = get_available_zainetto('ETC', test_realize, conn)
        
        if available < 0:
            print(f"   ✅ Zainetto disponibile corretto: €{available:.2f} (negativo = loss disponibile)")
        else:
            print(f"   ❌ Zainetto disponibile errato: €{available:.2f} (dovrebbe essere negativo)")
            return False
        
        # Verifica che OICR_ETF abbia zainetto separato
        oicr_available = get_available_zainetto('OICR_ETF', test_realize, conn)
        if oicr_available < 0:
            print(f"   ✅ Zainetto OICR_ETF separato: €{oicr_available:.2f}")
        else:
            print(f"   ⚠️  Nessun zainetto OICR_ETF disponibile (normale se non ci sono loss)")
        
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
        try:
            conn.rollback()
        except:
            pass
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = test_tax_engine()
    sys.exit(0 if success else 1)
