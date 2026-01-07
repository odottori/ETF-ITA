#!/usr/bin/env python3
"""
Execute Orders - ETF Italia Project v10
Bridge tra ordini generati e movimenti nel ledger (closed loop)
"""

import sys
import os
import json
import duckdb

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager
from fiscal.tax_engine import calculate_tax, create_tax_loss_carryforward, update_zainetto_usage

def check_cash_available(conn, required_cash):
    """Verifica cash disponibile prima di BUY"""
    
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
    
    return cash_balance >= required_cash, cash_balance

def check_position_available(conn, symbol, required_qty):
    """Verifica posizione disponibile prima di SELL"""
    
    position_check = conn.execute("""
    SELECT SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
    FROM fiscal_ledger 
    WHERE symbol = ? AND type IN ('BUY', 'SELL')
    """, [symbol]).fetchone()
    
    available_qty = position_check[0] if position_check and position_check[0] else 0
    return available_qty >= required_qty, available_qty

def execute_orders(orders_file=None, commit=False):
    """Esegue ordini da file e scrive nel fiscal_ledger"""
    
    print(" EXECUTE ORDERS - ETF Italia Project v10")
    print("=" * 60)
    
    pm = get_path_manager()
    config_path = str(pm.etf_universe_path)
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Trova file ordini più recente se non specificato
        if not orders_file:
            orders_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'orders')
            order_files = [f for f in os.listdir(orders_dir) if f.startswith('orders_') and f.endswith('.json')]
            if not order_files:
                print(" Nessun file ordini trovato")
                return False
            
            order_files.sort(reverse=True)  # Ordina per data (nome file)
            orders_file = os.path.join(orders_dir, order_files[0])
            print(f" File ordini selezionato: {orders_file}")
        
        # 2. Carica ordini
        with open(orders_file, 'r') as f:
            orders_data = json.load(f)
        
        orders = orders_data.get('orders', [])
        if not orders:
            print(" Nessun ordine da eseguire")
            return False
        
        print(f" Ordini da processare: {len(orders)}")
        
        # 3. Filtra solo ordini eseguibili (BUY/SELL)
        executable_orders = [o for o in orders if o['action'] in ['BUY', 'SELL'] and o['recommendation'] == 'TRADE']
        
        if not executable_orders:
            print(" Nessun ordine eseguibile (solo HOLD o raccomandazioni non TRADE)")
            return True
        
        print(f" Ordini eseguibili: {len(executable_orders)}")
        
        # 4. Inizia transazione
        if commit:
            conn.execute("BEGIN TRANSACTION")
        
        # 5. Processa ogni ordine
        executed_orders = []
        rejected_orders = []
        run_id = f"execute_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        for order in executable_orders:
            symbol = order['symbol']
            action = order['action']
            qty = order['qty']
            price = order['price']
            reason = order['reason']
            
            print(f"\n 🔄 {symbol}: {action} {qty:.0f} @ €{price:.2f}")
            print(f"    Reason: {reason}")
            
            # 5.1 Validazioni pre-esecuzione HARD CONTROLS
            if action == 'BUY':
                # Verifica cash disponibile
                position_value = qty * price
                commission_pct = config['universe']['core'][0]['cost_model']['commission_pct']
                commission = position_value * commission_pct
                if position_value < 1000:
                    commission = max(5.0, commission)
                
                # Stima slippage per calcolo cash richiesto
                volatility_data = conn.execute("""
                SELECT volatility_20d FROM risk_metrics 
                WHERE symbol = ? 
                ORDER BY date DESC LIMIT 1
                """, [symbol]).fetchone()
                
                volatility = volatility_data[0] if volatility_data and volatility_data[0] else 0.15
                slippage_bps = max(2, volatility * 0.5)
                slippage = position_value * (slippage_bps / 10000)
                
                total_required = position_value + commission + slippage
                cash_available, cash_balance = check_cash_available(conn, total_required)
                
                if not cash_available:
                    print(f"    ❌ CASH INSUFFICIENTE: richiesto €{total_required:.2f}, disponibile €{cash_balance:.2f}")
                    rejected_orders.append({
                        'symbol': symbol,
                        'action': action,
                        'qty': qty,
                        'price': price,
                        'reason': reason,
                        'reject_reason': f'CASH_INSUFFICIENTE: richiesto €{total_required:.2f}, disponibile €{cash_balance:.2f}',
                        'timestamp': datetime.now().isoformat()
                    })
                    continue
                
                print(f"    ✅ Cash OK: richiesto €{total_required:.2f}, disponibile €{cash_balance:.2f}")
                
            elif action == 'SELL':
                # Verifica posizione esistente
                position_available, available_qty = check_position_available(conn, symbol, qty)
                
                if not position_available:
                    print(f"    ❌ POSIZIONE INSUFFICIENTE: richiesto {qty:.0f}, disponibile {available_qty:.0f}")
                    rejected_orders.append({
                        'symbol': symbol,
                        'action': action,
                        'qty': qty,
                        'price': price,
                        'reason': reason,
                        'reject_reason': f'POSIZIONE_INSUFFICIENTE: richiesto {qty:.0f}, disponibile {available_qty:.0f}',
                        'timestamp': datetime.now().isoformat()
                    })
                    continue
                
                print(f"    ✅ Posizione OK: richiesto {qty:.0f}, disponibile {available_qty:.0f}")
            
            # 5.2 Calcola costi realistici (already estimated for BUY cash check)
            position_value = qty * price
            
            # Commissioni
            commission_pct = config['universe']['core'][0]['cost_model']['commission_pct']
            commission = position_value * commission_pct
            if position_value < 1000:
                commission = max(5.0, commission)
            
            # Slippage (basato su volatilità)
            volatility_data = conn.execute("""
            SELECT volatility_20d FROM risk_metrics 
            WHERE symbol = ? 
            ORDER BY date DESC LIMIT 1
            """, [symbol]).fetchone()
            
            volatility = volatility_data[0] if volatility_data and volatility_data[0] else 0.15
            slippage_bps = max(2, volatility * 0.5)
            slippage = position_value * (slippage_bps / 10000)
            
            total_fees = commission + slippage
            
            # 5.3 Calcola tax per vendite con logica zainetto
            tax_paid = 0.0
            if action == 'SELL':
                # Calcola realized gain per tax
                avg_buy_price = conn.execute("""
                SELECT AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price
                FROM fiscal_ledger 
                WHERE symbol = ? AND type IN ('BUY', 'SELL')
                """, [symbol]).fetchone()
                
                if avg_buy_price and avg_buy_price[0]:
                    avg_price = avg_buy_price[0]
                    if price > avg_price:
                        realized_gain = (price - avg_price) * qty
                        
                        # Usa logica fiscale completa con zainetto
                        tax_result = calculate_tax(realized_gain, symbol, datetime.now().date(), conn)
                        tax_paid = tax_result['tax_amount']
                        
                        print(f"    Gain: €{realized_gain:.2f}, Tax: €{tax_paid:.2f}")
                        print(f"    {tax_result['explanation']}")
                        
                        # Se usato zainetto, aggiornalo
                        if tax_result['zainetto_used'] > 0:
                            update_zainetto_usage(
                                symbol, 
                                tax_result['tax_category'], 
                                tax_result['zainetto_used'], 
                                datetime.now().date(), 
                                conn
                            )
                    else:
                        # Loss: crea zainetto
                        loss_amount = (price - avg_price) * qty  # Negativo
                        if loss_amount < -0.01:  # Soglia minima
                            zainetto_record = create_tax_loss_carryforward(
                                symbol, datetime.now().date(), loss_amount, conn
                            )
                            print(f"    Loss: €{loss_amount:.2f} -> zainetto creato")
                            print(f"    Scadenza: {zainetto_record['expires_at']}")
                        else:
                            print(f"    Loss minimo: €{loss_amount:.2f} (sotto soglia)")
            
            # 5.4 Arrotondamenti finanziari
            qty = Decimal(str(qty)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            price = Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_fees = Decimal(str(total_fees)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax_paid = Decimal(str(tax_paid)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # 5.5 Ottieni next ID per fiscal_ledger
            next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
            
            # 5.6 Inserisci in fiscal_ledger
            ledger_record = {
                'id': next_id,
                'date': datetime.now().date(),
                'type': action,
                'symbol': symbol,
                'qty': float(qty),
                'price': float(price),
                'fees': float(total_fees),
                'tax_paid': float(tax_paid),
                'pmc_snapshot': None,  # Will be calculated by update_ledger (Portfolio Market Value)
                'run_id': run_id
            }
            
            if commit:
                conn.execute("""
                INSERT INTO fiscal_ledger 
                (id, date, type, symbol, qty, price, fees, tax_paid, pmc_snapshot, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ledger_record['id'],
                    ledger_record['date'],
                    ledger_record['type'],
                    ledger_record['symbol'],
                    ledger_record['qty'],
                    ledger_record['price'],
                    ledger_record['fees'],
                    ledger_record['tax_paid'],
                    ledger_record['pmc_snapshot'],
                    ledger_record['run_id']
                ])
                
                print(f"    ✅ Eseguito - ID: {next_id}")
            else:
                print(f"    📋 Dry-run - ID: {next_id}")
            
            executed_orders.append(ledger_record)
            
            # 5.7 Registra in trade_journal per audit
            if commit:
                # Ottieni next ID per trade_journal
                next_journal_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM trade_journal").fetchone()[0]
                
                conn.execute("""
                INSERT INTO trade_journal 
                (id, run_id, symbol, signal_state, risk_scalar, explain_code, 
                 flag_override, override_reason, theoretical_price, realized_price, slippage_bps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    next_journal_id,
                    run_id,
                    symbol,
                    order.get('signal_state', 'UNKNOWN'),
                    order.get('risk_scalar', 0.0),
                    reason,
                    False,  # No override
                    None,   # No override reason
                    price,  # Theoretical price
                    price,  # Realized price (same for now)
                    slippage_bps
                ])
        
        # 6. Summary esecuzione
        print(f"\n ESECUZIONE COMPLETATA")
        print(f" Ordini processati: {len(executable_orders)}")
        print(f" Ordini eseguiti: {len(executed_orders)}")
        print(f" Ordini respinti: {len(rejected_orders)}")
        
        if rejected_orders:
            print(f"\n REJECT SUMMARY:")
            for reject in rejected_orders:
                print(f"  ❌ {reject['symbol']} {reject['action']}: {reject['reject_reason']}")
        
        if executed_orders:
            total_value = sum(o['qty'] * o['price'] for o in executed_orders)
            total_fees = sum(o['fees'] + o['tax_paid'] for o in executed_orders)
            
            print(f" Valore totale: €{total_value:,.2f}")
            print(f" Costi totali: €{total_fees:,.2f}")
            print(f" Run ID: {run_id}")
        
        # 7. Commit se richiesto
        if commit:
            conn.commit()
            print(f"\n ✅ Ordini COMMITTATI nel database")
        else:
            print(f"\n 📋 Dry-run completato - nessuna modifica salvata")
            try:
                conn.rollback()
            except:
                pass
        
        return True
        
    except Exception as e:
        print(f" Errore execute orders: {e}")
        if commit:
            conn.rollback()
        return False
        
    finally:
        conn.close()

def validate_orders_file(orders_file):
    """Valida file ordini prima dell'esecuzione"""
    
    try:
        with open(orders_file, 'r') as f:
            data = json.load(f)
        
        # Verifica struttura base
        required_fields = ['timestamp', 'dry_run', 'orders', 'summary']
        for field in required_fields:
            if field not in data:
                print(f"❌ Campo mancante: {field}")
                return False
        
        orders = data['orders']
        if not isinstance(orders, list):
            print("❌ Orders non è una lista")
            return False
        
        # Verifica struttura ordini
        for i, order in enumerate(orders):
            required_order_fields = ['symbol', 'action', 'qty', 'price', 'reason', 'recommendation']
            for field in required_order_fields:
                if field not in order:
                    print(f"❌ Ordine {i}: campo mancante {field}")
                    return False
            
            if order['action'] not in ['BUY', 'SELL', 'HOLD']:
                print(f"❌ Ordine {i}: action non valido {order['action']}")
                return False
            
            if order['recommendation'] not in ['TRADE', 'HOLD']:
                print(f"❌ Ordine {i}: recommendation non valido {order['recommendation']}")
                return False
        
        print(f"✅ File ordini valido: {len(orders)} ordini")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Errore parsing JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Errore validazione: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Execute Orders ETF Italia Project')
    parser.add_argument('--orders-file', help='Path to orders JSON file')
    parser.add_argument('--commit', action='store_true', help='Commit changes to database')
    
    args = parser.parse_args()
    
    # Valida file se specificato
    if args.orders_file and not validate_orders_file(args.orders_file):
        sys.exit(1)
    
    success = execute_orders(orders_file=args.orders_file, commit=args.commit)
    sys.exit(0 if success else 1)
