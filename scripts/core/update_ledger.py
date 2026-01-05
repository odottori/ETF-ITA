#!/usr/bin/env python3
"""
Update Ledger - ETF Italia Project v10
Aggiornamento ledger fiscale con cash interest e sanity check bloccante
"""

import sys
import os
import json
import duckdb
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def update_ledger(commit=False):
    """Aggiorna ledger con operazioni correnti"""
    
    print(" UPDATE LEDGER - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Sanity check bloccante
        print(" Sanity check...")
        if not sanity_check(conn):
            print(" SANITY CHECK FAILED - Operazione bloccata")
            return False
        
        print(" Sanity check passed")
        
        # 2. Calcolo cash interest mensile
        print(" Calcolo cash interest...")
        
        # Ottieni cash balance attuale
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
        
        print(f" Cash balance attuale: €{cash_balance:,.2f}")
        
        # Verifica se è già stato pagato interesse questo mese
        current_month = datetime.now().replace(day=1).date()
        last_interest = conn.execute("""
        SELECT MAX(date) as last_interest_date
        FROM fiscal_ledger 
        WHERE type = 'INTEREST' AND date >= ?
        """, [current_month]).fetchone()[0]
        
        if last_interest:
            print(f" Interesse già pagato questo mese: {last_interest}")
            interest_amount = 0.0
        else:
            # Calcola interesse mensile
            cash_rate = config['settings']['cash_interest_rate']
            monthly_rate = cash_rate / 12
            interest_amount = cash_balance * monthly_rate
            
            print(f" Tasso cash interest: {cash_rate:.1%} annualizzato")
            print(f" Interesse mensile: €{interest_amount:.2f}")
            
            if commit and interest_amount > 0:
                # Inserisci record INTEREST
                next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
                
                conn.execute("""
                INSERT INTO fiscal_ledger 
                (id, date, type, symbol, qty, price, fees, tax_paid, pmc_snapshot, run_id)
                VALUES (?, ?, 'INTEREST', 'CASH', ?, 1.0, 0.0, 0.0, ?, ?)
                """, [
                    next_id, 
                    datetime.now().date(),
                    interest_amount,
                    cash_balance + interest_amount,
                    f"ledger_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                ])
                
                print(f" Interesse registrato: €{interest_amount:.2f}")
        
        # 3. Verifica posizioni correnti
        print("\n Posizioni correnti:")
        
        positions = conn.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
            AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price,
            COUNT(*) as trades
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        ORDER BY symbol
        """).fetchall()
        
        if positions:
            for symbol, qty, avg_price, trades in positions:
                # Ottieni prezzo attuale
                current_price = conn.execute("""
                SELECT adj_close FROM market_data 
                WHERE symbol = ? 
                ORDER BY date DESC 
                LIMIT 1
                """, [symbol]).fetchone()
                
                if current_price:
                    market_value = qty * current_price[0]
                    pnl = (current_price[0] - avg_price) * qty
                    
                    print(f"  {symbol}: {qty:,.0f} @ €{avg_price:.2f} → €{current_price[0]:.2f}")
                    print(f"    Market value: €{market_value:,.2f} | PnL: €{pnl:+,.2f} | Trades: {trades}")
                else:
                    print(f"  {symbol}: {qty:,.0f} @ €{avg_price:.2f} (no price data)")
        else:
            print("  Nessuna posizione aperta")
        
        # 4. Summary finanziario
        print(f"\n Summary finanziario:")
        total_value = conn.execute("""
        SELECT SUM(market_value) FROM portfolio_summary
        """).fetchone()[0] or 0
        
        portfolio_value = cash_balance + total_value
        print(f"  Cash: €{cash_balance:,.2f}")
        print(f"  Positions: €{total_value:,.2f}")
        print(f"  Portfolio value: €{portfolio_value:,.2f}")
        
        # 5. Commit se richiesto
        if commit:
            conn.commit()
            print(f"\n Ledger aggiornato con successo")
            print(f" Run ID: ledger_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        else:
            print(f"\n Dry-run completato - nessuna modifica salvata")
            try:
                conn.rollback()
            except:
                pass  # Ignora se non c'è transazione attiva
        
        return True
        
    except Exception as e:
        print(f" Errore update ledger: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def sanity_check(conn):
    """Controllo di integrità bloccante"""
    
    try:
        # 1. Posizioni negative
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
            print(f" Posizioni negative trovate: {negative_positions}")
            return False
        
        # 2. Cash negativo
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
            print(f" Cash balance negativo: €{cash_balance:,.2f}")
            return False
        
        # 3. PMC coerenti
        pmc_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE pmc_snapshot < 0
        """).fetchone()[0]
        
        if pmc_issues > 0:
            print(f" PMC negativi trovati: {pmc_issues}")
            return False
        
        # 4. Date coerenti
        future_dates = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE date > CURRENT_DATE
        """).fetchone()[0]
        
        if future_dates > 0:
            print(f" Date future trovate: {future_dates}")
            return False
        
        return True
        
    except Exception as e:
        print(f" Errore sanity check: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update ledger ETF Italia Project')
    parser.add_argument('--commit', action='store_true', help='Commit changes to database')
    
    args = parser.parse_args()
    
    success = update_ledger(commit=args.commit)
    sys.exit(0 if success else 1)
