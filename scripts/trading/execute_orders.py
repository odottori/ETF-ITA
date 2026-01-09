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
from utils.universe_helper import get_universe_symbols
from utils.asof_date import compute_asof_date
from fiscal.tax_engine import calculate_tax, create_tax_loss_carryforward, update_zainetto_usage

from fiscal.pmc_engine import load_position_state, apply_buy, estimate_sell_gain
from utils.universe_helper import get_cost_model_for_symbol, get_execution_model_for_symbol


def _table_columns(conn, table_name: str):
    """Ritorna set delle colonne presenti in una tabella (DuckDB)."""
    cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {c[1] for c in cols}


def _has_column(conn, table_name: str, col_name: str) -> bool:
    return col_name in _table_columns(conn, table_name)


def _table_exists(conn, table_name: str) -> bool:
    """True se la tabella esiste nel catalog DuckDB."""
    try:
        rows = conn.execute("SHOW TABLES").fetchall()
        tables = {r[0] for r in rows}
        return table_name in tables
    except Exception:
        # Fallback ultra-safe
        try:
            conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            return True
        except Exception:
            return False

def check_cash_available(conn, required_cash, run_type=None):
    """Verifica cash disponibile prima di BUY"""

    if run_type and _has_column(conn, 'fiscal_ledger', 'run_type'):
        cash_balance = conn.execute("""
        SELECT COALESCE(SUM(CASE 
            WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
            WHEN type = 'BUY' THEN -(qty * price + fees)
            WHEN type = 'INTEREST' THEN qty
            ELSE 0 
        END), 0) as cash_balance
        FROM fiscal_ledger
        WHERE run_type = ?
        """, [run_type]).fetchone()[0]
    else:
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

def check_position_available(conn, symbol, required_qty, run_type=None):
    """Verifica posizione disponibile prima di SELL"""

    if run_type and _has_column(conn, 'fiscal_ledger', 'run_type'):
        position_check = conn.execute("""
        SELECT SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
        FROM fiscal_ledger 
        WHERE symbol = ? AND type IN ('BUY', 'SELL')
        AND run_type = ?
        """, [symbol, run_type]).fetchone()
    else:
        position_check = conn.execute("""
        SELECT SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
        FROM fiscal_ledger 
        WHERE symbol = ? AND type IN ('BUY', 'SELL')
        """, [symbol]).fetchone()
    
    available_qty = position_check[0] if position_check and position_check[0] else 0
    return available_qty >= required_qty, available_qty

def execute_orders(orders_file=None, commit=False, order_date=None, run_type='PRODUCTION'):
    """Esegue ordini da file e scrive nel fiscal_ledger
    
    Args:
        orders_file: Path al file ordini JSON
        commit: Se True, committa le modifiche al DB
        order_date: Data ordine (default: oggi). Usato per backtest storici
        run_type: 'PRODUCTION' o 'BACKTEST'
    """
    
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

    market_data_exists = _table_exists(conn, 'market_data')
    
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
        run_id = orders_data.get('run_id') or f"execute_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Data ordine: preferisci as_of_date dal file ordini; fallback su as-of coerente da DB
        if order_date is None:
            file_as_of = orders_data.get('as_of_date')
            if file_as_of:
                if isinstance(file_as_of, str):
                    order_date = datetime.strptime(file_as_of, '%Y-%m-%d').date()
                else:
                    order_date = file_as_of
            else:
                # fallback: calcola as-of dal DB (coverage-threshold, venue) evitando 'today'
                pm = get_path_manager()
                config_path = str(pm.etf_universe_path)
                coverage_threshold = float(orders_data.get('coverage_threshold', 0.8))
                venue = 'BIT'
                try:
                    with open(config_path, 'r') as cf:
                        cfg = json.load(cf)
                    symbols = get_universe_symbols(cfg, include_benchmark=False)
                    computed = compute_asof_date(conn, symbols, coverage_threshold=coverage_threshold, venue=venue)

                    if computed:
                        order_date = computed
                    elif market_data_exists:
                        order_date = conn.execute("SELECT MAX(date) FROM market_data").fetchone()[0]
                    else:
                        # Test harness / DB minimale: fallback su risk_metrics o oggi
                        order_date = conn.execute("SELECT MAX(date) FROM risk_metrics").fetchone()[0] or datetime.now().date()
                except Exception:
                    if market_data_exists:
                        order_date = conn.execute("SELECT MAX(date) FROM market_data").fetchone()[0] or datetime.now().date()
                    else:
                        order_date = conn.execute("SELECT MAX(date) FROM risk_metrics").fetchone()[0] or datetime.now().date()
        elif isinstance(order_date, str):
            order_date = datetime.strptime(order_date, '%Y-%m-%d').date()
        
        fiscal_cols = _table_columns(conn, 'fiscal_ledger')

        for order in executable_orders:
            symbol = order['symbol']
            action = order['action']
            qty = order['qty']
            price = order['price']
            reason = order['reason']
            # Guardrail HARD: non eseguire BUY/SELL se manca market_data per (symbol, order_date)
            # (Se la tabella market_data non esiste, siamo in un DB minimale / test harness: non bloccare.)
            if market_data_exists:
                md_ok = conn.execute(
                    "SELECT 1 FROM market_data WHERE symbol = ? AND date = ? LIMIT 1",
                    [symbol, order_date]
                ).fetchone()
                if not md_ok:
                    print(f"    ⛔ REJECT {action} {symbol} - market_data mancante per {order_date}")
                    order['recommendation'] = 'REJECT'
                    order['reject_reason'] = 'MARKET_DATA_MISSING'
                    rejected_orders.append({
                        'symbol': symbol,
                        'action': action,
                        'order_date': str(order_date),
                        'reason': 'MARKET_DATA_MISSING'
                    })
                    continue
            else:
                # Informativo (una sola volta) - non spam
                if not globals().get('_WARNED_NO_MARKET_DATA', False):
                    globals()['_WARNED_NO_MARKET_DATA'] = True
                    print("    ⚠️ market_data assente nel DB: skip guardrail market_data (modalità test/harness)")

            print(f"\n 🔄 {symbol}: {action} {qty:.0f} @ €{price:.2f}")
            print(f"    Reason: {reason}")
            
            # 5.1 Validazioni pre-esecuzione HARD CONTROLS
            if action == 'BUY':
                # Verifica cash disponibile
                position_value = qty * price
                cost_model = get_cost_model_for_symbol(config, symbol)
                commission_pct = float(cost_model.get('commission_pct', 0.001))
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
                base_slippage_bps = float(cost_model.get('slippage_bps', 5))
                # EUR/ETF: slippage cresce con vol (annualizzata). Converte vol in bps con fattore prudenziale.
                vol_slippage_bps = max(0.0, float(volatility) * 100.0 * 0.5)  # es. 15% vol -> ~7.5bps
                slippage_bps = max(base_slippage_bps, vol_slippage_bps)
                slippage = position_value * (slippage_bps / 10000)
                
                total_required = position_value + commission + slippage
                cash_available, cash_balance = check_cash_available(conn, total_required, run_type=run_type)
                
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
                position_available, available_qty = check_position_available(conn, symbol, qty, run_type=run_type)
                
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
            
            # 5.2 Calcola costi realistici (per simbolo)
            position_value = qty * price
            cost_model = get_cost_model_for_symbol(config, symbol)
            commission_pct = float(cost_model.get('commission_pct', 0.001))
            commission = position_value * commission_pct
            if position_value < 1000:
                commission = max(5.0, commission)

            # Slippage (basato su volatilità annualizzata → bps)
            volatility_data = conn.execute(
                """
                SELECT volatility_20d FROM risk_metrics 
                WHERE symbol = ? 
                ORDER BY date DESC LIMIT 1
                """,
                [symbol],
            ).fetchone()
            volatility = volatility_data[0] if volatility_data and volatility_data[0] else 0.15
            base_slippage_bps = float(cost_model.get('slippage_bps', 5))
            vol_slippage_bps = max(0.0, float(volatility) * 100.0 * 0.5)  # es. 15% -> ~7.5bps
            slippage_bps = max(base_slippage_bps, vol_slippage_bps)
            slippage = position_value * (slippage_bps / 10000)

            total_fees = commission + slippage

            # 5.3 Calcola tax per vendite via PMC (no side effects in dry-run)
            tax_paid = 0.0
            realized_gain = 0.0
            pmc_snapshot = None
            state_before = load_position_state(conn, symbol, run_type=run_type)

            if action == 'SELL':
                realized_gain, pmc_used = estimate_sell_gain(state_before, qty, price, total_fees)
                pmc_snapshot = pmc_used

                if realized_gain > 0.01:
                    tax_result = calculate_tax(realized_gain, symbol, order_date, conn, run_type=run_type)
                    tax_paid = float(tax_result['tax_amount'])
                    print(f"    Gain (PMC): €{realized_gain:.2f}, Tax: €{tax_paid:.2f}")
                    print(f"    {tax_result['explanation']}")

                    if commit and tax_result.get('zainetto_used', 0) > 0:
                        update_zainetto_usage(
                            symbol,
                            tax_result['tax_category'],
                            tax_result['zainetto_used'],
                            order_date,
                            conn,
                            run_type=run_type,
                        )
                elif realized_gain < -0.01:
                    print(f"    Loss (PMC): €{realized_gain:.2f}")
                    if commit:
                        zainetto_record = create_tax_loss_carryforward(symbol, order_date, realized_gain, conn, run_type=run_type)
                        print(f"    Loss -> zainetto creato (scadenza: {zainetto_record['expires_at']})")
            else:
                # BUY: calcola nuovo PMC post-trade
                new_state = apply_buy(state_before, qty, price, total_fees)
                pmc_snapshot = new_state.pmc
            
            # 5.4 Arrotondamenti finanziari
            qty = Decimal(str(qty)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            price = Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_fees = Decimal(str(total_fees)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax_paid = Decimal(str(tax_paid)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # 5.5 Ottieni next ID per fiscal_ledger
            next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
            
            # 5.6 Inserisci in fiscal_ledger (FIX BUG #2-4: order_date, run_type, decision_path, reason_code)
            execution_price_mode = (
                order.get('execution_price_mode')
                or orders_data.get('execution_price_mode')
                or get_execution_model_for_symbol(config, symbol)
                or 'CLOSE_SAME_DAY_SLIPPAGE'
            )

            ledger_record = {
                'id': next_id,
                'date': order_date,
                'type': action,
                'symbol': symbol,
                'qty': float(qty),
                'price': float(price),
                'fees': float(total_fees),
                'tax_paid': float(tax_paid),
                'pmc_snapshot': float(pmc_snapshot) if pmc_snapshot is not None else None,
                'run_id': run_id,
                'run_type': run_type,
                'decision_path': order.get('decision_path') or 'STRATEGY_ENGINE',
                'reason_code': order.get('reason_code') or reason,
                'execution_price_mode': execution_price_mode,
                'source_order_id': order.get('source_order_id'),
                # Optional holding-period metadata (se presenti nel file ordini)
                'entry_date': order.get('entry_date'),
                'entry_score': order.get('entry_score'),
                'expected_holding_days': order.get('expected_holding_days'),
                'expected_exit_date': order.get('expected_exit_date'),
                'exit_reason': order.get('exit_reason'),
                'holding_days_actual': order.get('holding_days_actual'),
            }
            
            if commit:
                # Inserimento schema-robust: usa solo le colonne presenti
                ordered_cols = [
                    'id', 'date', 'type', 'symbol', 'qty', 'price', 'fees', 'tax_paid', 'pmc_snapshot', 'run_id',
                    'run_type', 'decision_path', 'reason_code', 'execution_price_mode', 'source_order_id',
                    'entry_date', 'entry_score', 'expected_holding_days', 'expected_exit_date',
                    'exit_reason', 'holding_days_actual'
                ]
                insert_cols = [c for c in ordered_cols if c in fiscal_cols]
                placeholders = ', '.join(['?'] * len(insert_cols))
                col_list = ', '.join(insert_cols)

                conn.execute(
                    f"INSERT INTO fiscal_ledger ({col_list}) VALUES ({placeholders})",
                    [ledger_record[c] for c in insert_cols]
                )
                
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
