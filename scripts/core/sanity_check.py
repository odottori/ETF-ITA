#!/usr/bin/env python3
"""
Sanity Check Bloccante - ETF Italia Project v003
Validazione integrità sistema con controlli bloccanti
"""

import sys
import os
import duckdb

from datetime import datetime

# Aggiungi path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager

def sanity_check(conn):
    """Controllo di integrità bloccante"""
    
    print("🔍 SANITY CHECK - BLOCCANTE")
    print("=" * 50)
    
    errors = []
    warnings = []
    
    try:
        # 1. Posizioni negative
        print("1️⃣ Verifica posizioni negative...")
        negative_positions = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT symbol, SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL')
            GROUP BY symbol
            HAVING net_qty < 0
        )
        """).fetchone()[0]
        
        if negative_positions > 0:
            errors.append(f"Posizioni negative trovate: {negative_positions}")
            print(f"   ❌ {negative_positions} posizioni negative")
        else:
            print("   ✅ Nessuna posizione negativa")
        
        # 2. Cash negativo
        print("2️⃣ Verifica cash balance...")
        cash_balance = conn.execute("""
        SELECT COALESCE(SUM(CASE 
            WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
            WHEN type = 'BUY' THEN -(qty * price + fees)
            WHEN type = 'INTEREST' THEN qty
            ELSE 0 
        END), 0) as cash_balance
        FROM fiscal_ledger
        """).fetchone()[0]
        
        if cash_balance < 0:
            errors.append(f"Cash balance negativo: €{cash_balance:,.2f}")
            print(f"   ❌ Cash negativo: €{cash_balance:,.2f}")
        else:
            print(f"   ✅ Cash positivo: €{cash_balance:,.2f}")
        
        # 3. PMC coerenti
        print("3️⃣ Verifica PMC...")
        pmc_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE pmc_snapshot < 0
        """).fetchone()[0]
        
        if pmc_issues > 0:
            errors.append(f"PMC negativi trovati: {pmc_issues}")
            print(f"   ❌ {pmc_issues} PMC negativi")
        else:
            print("   ✅ Tutti i PMC positivi")
        
        # 4. Invarianti contabili
        print("4️⃣ Verifica invarianti contabili...")
        accounting_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE (type = 'BUY' AND qty <= 0) OR (type = 'SELL' AND qty <= 0) OR (price <= 0)
        """).fetchone()[0]
        
        if accounting_issues > 0:
            errors.append(f"Invarianti contabili violate: {accounting_issues}")
            print(f"   ❌ {accounting_issues} invarianti violate")
        else:
            print("   ✅ Invarianti contabili OK")
        
        # 5. No future data leak
        print("5️⃣ Verifica future data leak...")
        max_ledger_date = conn.execute("""
        SELECT MAX(date) FROM fiscal_ledger
        """).fetchone()[0]
        
        max_market_date = conn.execute("""
        SELECT MAX(date) FROM market_data
        """).fetchone()[0]
        
        if max_ledger_date and max_market_date:
            if max_ledger_date > max_market_date:
                errors.append(f"Future data leak: ledger {max_ledger_date} > market {max_market_date}")
                print(f"   ❌ Future data leak: ledger {max_ledger_date} > market {max_market_date}")
            else:
                print(f"   ✅ No future data leak (ledger: {max_ledger_date}, market: {max_market_date})")
        
        # 6. Trading calendar gaps
        print("6️⃣ Verifica trading calendar gaps...")
        calendar_gaps = conn.execute("""
        SELECT COUNT(*) FROM trading_calendar tc
        WHERE tc.is_open = TRUE 
        AND NOT EXISTS (
            SELECT 1 FROM market_data md 
            WHERE md.date = tc.date 
            AND EXISTS (SELECT 1 FROM market_data WHERE symbol = 'IEAC.MI' AND date = tc.date)
        )
        """).fetchone()[0]
        
        if calendar_gaps > 0:
            warnings.append(f"Trading calendar gaps: {calendar_gaps}")
            print(f"   ⚠️  {calendar_gaps} giorni trading senza dati")
        else:
            print("   ✅ Nessun gap nel trading calendar")
        
        # 7. Ledger vs market data coherence
        print("7️⃣ Verifica coerenza ledger vs market data...")
        coherence_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger fl
        WHERE NOT EXISTS (
            SELECT 1 FROM market_data md 
            WHERE md.symbol = fl.symbol AND md.date = fl.date
        )
        AND fl.type IN ('BUY', 'SELL')
        """).fetchone()[0]
        
        if coherence_issues > 0:
            warnings.append(f"Ledger/market data mismatch: {coherence_issues}")
            print(f"   ⚠️  {coherence_issues} record ledger senza market data")
        else:
            print("   ✅ Ledger e market data coerenti")
        
        # 8. Tax bucket coherence
        print("8️⃣ Verifica tax bucket coherence...")
        tax_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE type = 'SELL' 
        AND (tax_paid < 0 OR tax_paid IS NULL)
        """).fetchone()[0]
        
        if tax_issues > 0:
            warnings.append(f"Tax bucket issues: {tax_issues}")
            print(f"   ⚠️  {tax_issues} vendite con tax bucket incoerente")
        else:
            print("   ✅ Tax bucket coerente")
        
        # 9. Portfolio value consistency
        print("9️⃣ Verifica consistenza valore portafoglio...")
        portfolio_query = """
        WITH current_positions AS (
            SELECT 
                symbol,
                SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
                AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_price
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL')
            GROUP BY symbol
            HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        ),
        current_prices AS (
            SELECT md.symbol, md.close as current_price
            FROM market_data md
            WHERE md.date = (SELECT MAX(date) FROM market_data)
        ),
        portfolio_value AS (
            SELECT 
                SUM(cp.qty * cp2.current_price) as market_value,
                SUM(cp.qty * cp.avg_price) as cost_basis
            FROM current_positions cp
            JOIN current_prices cp2 ON cp.symbol = cp2.symbol
        )
        SELECT market_value, cost_basis FROM portfolio_value
        """
        
        portfolio_result = conn.execute(portfolio_query).fetchone()
        if portfolio_result:
            market_value, cost_basis = portfolio_result
            if market_value < 0:
                errors.append(f"Portfolio value negativo: €{market_value:,.2f}")
                print(f"   ❌ Portfolio value negativo: €{market_value:,.2f}")
            else:
                print(f"   ✅ Portfolio value: €{market_value:,.2f}")
        
        # Risultato finale
        print("\n" + "=" * 50)
        print("📊 RIEPILOGO SANITY CHECK")
        
        if errors:
            print(f"❌ ERRORI CRITICI ({len(errors)}):")
            for error in errors:
                print(f"   - {error}")
        
        if warnings:
            print(f"⚠️  WARNING ({len(warnings)}):")
            for warning in warnings:
                print(f"   - {warning}")
        
        if not errors and not warnings:
            print("✅ Tutti i controlli superati")
        
        return len(errors) == 0
        
    except Exception as e:
        print(f"❌ Errore durante sanity check: {e}")
        return False

def main():
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return 1
    
    conn = duckdb.connect(db_path)
    
    try:
        success = sanity_check(conn)
        
        if success:
            print("\n✅ Sanity check PASSED")
            return 0
        else:
            print("\n❌ Sanity check FAILED")
            return 1
            
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
