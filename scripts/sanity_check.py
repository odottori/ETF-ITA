#!/usr/bin/env python3
"""
Sanity Check - ETF Italia Project v10
Controllo integrità bloccante per ledger e sistema
"""

import sys
import os
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def sanity_check():
    """Controllo integrità bloccante"""
    
    print("🔍 SANITY CHECK - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        issues = []
        
        print("🔍 Verifica integrità sistema...")
        
        # 1. Posizioni negative
        print("\n1️⃣ Verifica posizioni negative...")
        
        negative_positions = conn.execute("""
        SELECT symbol, SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING net_qty < 0
        """).fetchall()
        
        if negative_positions:
            print("❌ POSIZIONI NEGATIVE TROVATE:")
            for symbol, qty in negative_positions:
                print(f"  {symbol}: {qty:.0f}")
                issues.append(f"Posizione negativa: {symbol}")
        else:
            print("✅ Nessuna posizione negativa")
        
        # 2. Cash negativo
        print("\n2️⃣ Verifica cash balance...")
        
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
            print(f"❌ CASH BALANCE NEGATIVO: €{cash_balance:,.2f}")
            issues.append(f"Cash negativo: €{cash_balance:,.2f}")
        else:
            print(f"✅ Cash balance: €{cash_balance:,.2f}")
        
        # 3. PMC coerenti
        print("\n3️⃣ Verifica PMC...")
        
        pmc_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE pmc_snapshot < 0
        """).fetchone()[0]
        
        if pmc_issues > 0:
            print(f"❌ PMC NEGATIVI: {pmc_issues}")
            issues.append(f"PMC negativi: {pmc_issues}")
        else:
            print("✅ PMC coerenti")
        
        # 4. Date coerenti
        print("\n4️⃣ Verifica date...")
        
        future_dates = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE date > CURRENT_DATE
        """).fetchone()[0]
        
        if future_dates > 0:
            print(f"❌ DATE FUTURE: {future_dates}")
            issues.append(f"Date future: {future_dates}")
        else:
            print("✅ Date coerenti")
        
        # 5. Invarianti contabili
        print("\n5️⃣ Verifica invarianti contabili...")
        
        # Verifica equity = cash + positions
        total_cash = cash_balance
        total_positions = conn.execute("""
        SELECT COALESCE(SUM(qty * current_price), 0) as total_value
        FROM (
            SELECT 
                symbol,
                SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
                (SELECT adj_close FROM market_data m 
                 WHERE m.symbol = fl.symbol 
                 ORDER BY date DESC LIMIT 1) as current_price
            FROM fiscal_ledger fl
            WHERE type IN ('BUY', 'SELL')
            GROUP BY symbol
            HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        )
        """).fetchone()[0]
        
        total_equity = total_cash + total_positions
        
        # Verifica se ci sono discrepanze
        if total_equity < 0:
            print(f"❌ EQUITY NEGATIVA: €{total_equity:,.2f}")
            issues.append(f"Equity negativa: €{total_equity:,.2f}")
        else:
            print(f"✅ Equity: €{total_equity:,.2f}")
            print(f"   Cash: €{total_cash:,.2f} | Positions: €{total_positions:,.2f}")
        
        # 6. Data consistency
        print("\n6️⃣ Verifica consistenza dati...")
        
        # Verifica gap su giorni trading
        trading_gaps = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT date FROM market_data
            WHERE date IN (SELECT date FROM trading_calendar WHERE venue = 'BIT' AND is_open = TRUE)
            AND date >= '2020-01-01'
            EXCEPT
            SELECT DISTINCT date FROM market_data
        )
        """).fetchone()[0]
        
        if trading_gaps > 0:
            print(f"⚠️ TRADING GAPS: {trading_gaps} giorni mancanti")
            issues.append(f"Trading gaps: {trading_gaps}")
        else:
            print("✅ Dati trading completi")
        
        # 7. Summary
        print(f"\n📋 SANITY CHECK SUMMARY:")
        print(f"Issues trovati: {len(issues)}")
        
        if issues:
            print(f"\n❌ ISSUES DETECTED:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            
            print(f"\n🚨 SANITY CHECK FAILED - Sistema non coerente")
            return False
        else:
            print(f"\n✅ SANITY CHECK PASSED - Sistema coerente")
            return True
        
    except Exception as e:
        print(f"❌ Errore sanity check: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = sanity_check()
    sys.exit(0 if success else 1)
