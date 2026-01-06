#!/usr/bin/env python3
"""
Strategy Engine - ETF Italia Project v10
Motore strategia con dry-run e cost model realistico
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_manager import get_session_manager
from sequence_runner import run_sequence_from
from implement_risk_controls import check_stop_loss_trailing_stop, calculate_portfolio_value, calculate_target_weights, calculate_current_weights

def strategy_engine(dry_run=True, commit=False):
    """Motore strategia con dry-run"""
    
    print(" STRATEGY ENGINE - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Ottieni segnali correnti
        print(" Caricamento segnali correnti...")
        
        current_signals = conn.execute("""
        SELECT symbol, signal_state, risk_scalar, explain_code
        FROM signals 
        WHERE date = (SELECT MAX(date) FROM signals)
        ORDER BY symbol
        """).fetchall()
        
        if not current_signals:
            print(" Nessun segnale disponibile")
            return False
        
        # 2. Ottieni posizioni correnti
        print(" Analisi posizioni correnti...")
        
        positions = conn.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
            AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        """).fetchall()
        
        positions_dict = {symbol: {'qty': qty, 'avg_buy_price': avg_buy_price if avg_buy_price else 0} for symbol, qty, avg_buy_price in positions}
        
        # 3. Ottieni prezzi correnti
        print(" Caricamento prezzi correnti...")
        
        current_prices = {}
        for symbol, signal_state, risk_scalar, explain_code in current_signals:
            price_data = conn.execute("""
            SELECT close, adj_close, volume, volatility_20d
            FROM risk_metrics 
            WHERE symbol = ? AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = ?)
            """, [symbol, symbol]).fetchone()
            
            if price_data:
                current_prices[symbol] = {
                    'close': price_data[0],
                    'adj_close': price_data[1],
                    'volume': price_data[2],
                    'volatility_20d': price_data[3]
                }
        
        # 4. Calcola portfolio value reale da ledger
        print(" Calcolo portfolio value da ledger...")
        portfolio_value = calculate_portfolio_value(conn)
        print(f" Portfolio value attuale: €{portfolio_value:,.2f}")
        
        # 5. Calcola pesi target e attuali
        target_weights = calculate_target_weights(config, portfolio_value)
        current_weights = calculate_current_weights(conn, portfolio_value)
        
        print(f" Portfolio value attuale: €{portfolio_value:,.2f}")
        print(f" Pesi target: {target_weights}")
        print(f" Pesi attuali: {current_weights}")
        
        # 6. Processa segnali con integrato rebalancing deterministico
        rebalance_threshold = 0.05  # 5% deviation threshold
        orders = []
        
        print(" Elaborazione segnali con rebalancing integrato...")
        
        for symbol, signal_state, risk_scalar, explain_code in current_signals:
            if symbol not in current_prices:
                print(f"️ {symbol}: Nessun prezzo disponibile")
                continue
            
            current_price = current_prices[symbol]['close']
            current_vol = current_prices[symbol]['volatility_20d']
            
            # 6.1 Check stop-loss/trailing stop PRIMA di qualsiasi decisione
            stop_action, stop_reason = check_stop_loss_trailing_stop(config, symbol, current_price, positions_dict)
            
            if stop_action == 'SELL':
                # Stop-loss/trailing stop triggered - force sell
                if symbol in positions_dict:
                    qty = positions_dict[symbol]['qty']
                    
                    # Costi vendita
                    position_value = qty * current_price
                    commission_pct = config['universe']['core'][0]['cost_model']['commission_pct']
                    commission = position_value * commission_pct
                    if position_value < 1000:
                        commission = max(5.0, commission)
                    
                    slippage_bps = max(2, current_vol * 0.5)
                    slippage = position_value * (slippage_bps / 10000)
                    
                    # Tax su gain
                    avg_price = positions_dict[symbol]['avg_price']
                    if current_price > avg_price:
                        realized_gain = (current_price - avg_price) * qty
                        tax_estimate = realized_gain * 0.26
                    else:
                        tax_estimate = 0.0
                    
                    orders.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'qty': qty,
                        'price': current_price,
                        'reason': stop_reason,
                        'expected_alpha_est': 0.0,
                        'fees_est': commission + slippage,
                        'tax_friction_est': tax_estimate,
                        'do_nothing_score': 0.0,
                        'recommendation': 'FORCE_SELL'
                    })
                    print(f"🛑 {symbol}: STOP LOSS TRIGGERED - {stop_reason}")
                continue
            
            # 6.2 Check rebalancing need (solo se nessun segnale attivo)
            target_weight = target_weights.get(symbol, 0.0)
            current_weight = current_weights.get(symbol, 0.0)
            weight_deviation = abs(target_weight - current_weight)
            
            needs_rebalance = (weight_deviation > rebalance_threshold and 
                             signal_state not in ['RISK_ON', 'RISK_OFF'])
            
            if needs_rebalance:
                target_position_value = portfolio_value * target_weight
                current_position_value = portfolio_value * current_weight
                
                target_qty = target_position_value / current_price
                current_qty = positions_dict.get(symbol, {}).get('qty', 0)
                
                qty_diff = target_qty - current_qty
                
                if abs(qty_diff) > 0:
                    action = 'BUY' if qty_diff > 0 else 'SELL'
                    
                    # Costi per rebalancing
                    position_value = abs(qty_diff) * current_price
                    commission_pct = config['universe']['core'][0]['cost_model']['commission_pct']
                    commission = position_value * commission_pct
                    if position_value < 1000:
                        commission = max(5.0, commission)
                    
                    slippage_bps = max(2, current_vol * 0.5)
                    slippage = position_value * (slippage_bps / 10000)
                    
                    orders.append({
                        'symbol': symbol,
                        'action': action,
                        'qty': abs(qty_diff),
                        'price': current_price,
                        'reason': f'REBALANCE_{weight_deviation:.1%}_DEVIATION',
                        'expected_alpha_est': 0.0,
                        'fees_est': commission + slippage,
                        'tax_friction_est': 0.0,
                        'do_nothing_score': -1.0,  # Force rebalancing
                        'recommendation': 'TRADE'
                    })
                    print(f"    🔄 REBALANCE {symbol}: {action} {abs(qty_diff):.0f} shares (dev: {weight_deviation:.1%})")
                continue
            
            # 6.3 Processa segnali (solo se RISK_ON/OFF)
            if signal_state == 'RISK_ON':
                # Position sizing basato su risk scalar
                position_value = portfolio_value * risk_scalar * 0.3  # 30% max allocation
                
                # Volatility targeting
                if current_vol > 0:
                    target_vol = config['settings']['volatility_target']
                    vol_scalar = target_vol / current_vol
                    vol_scalar = min(1.0, vol_scalar)
                    vol_scalar = max(config['risk_management']['risk_scalar_floor'], vol_scalar)
                    position_value *= vol_scalar
                
                qty_target = position_value / current_price
                
                # Costi realistici
                commission_pct = config['universe']['core'][0]['cost_model']['commission_pct']
                slippage_bps = max(2, current_vol * 0.5)  # Slippage dinamico
                
                commission = position_value * commission_pct
                if position_value < 1000:
                    commission = max(5.0, commission)  # Min commission
                
                slippage = position_value * (slippage_bps / 10000)
                
                # TER drag giornaliero
                ter = config['universe']['core'][0]['ter']
                ter_daily = (1 + ter) ** (1/252) - 1
                ter_drag = position_value * ter_daily
                
                # Tax friction estimate
                if symbol in positions_dict:
                    avg_price = positions_dict[symbol]['avg_buy_price']
                    if current_price > avg_price:
                        unrealized_gain = (current_price - avg_price) * positions_dict[symbol]['qty']
                        tax_estimate = unrealized_gain * 0.26  # 26% su gain
                    else:
                        tax_estimate = 0.0
                else:
                    tax_estimate = 0.0
                
                total_cost = commission + slippage + ter_drag
                
                # Expected alpha modellistico basato su:
                # 1. Risk scalar (segnale di momentum/trend)
                # 2. Volatilità inversa (risk-adjusted return)
                # 3. Regime di mercato implicito nel signal
                base_alpha = 0.08  # 8% base annual return expectation
                
                # Adjust per risk scalar (più alto = più confidente)
                risk_adjusted_alpha = base_alpha * risk_scalar
                
                # Volatility adjustment (lower vol = higher risk-adjusted return)
                if current_vol > 0:
                    vol_adjustment = min(1.5, 0.10 / current_vol)  # Cap a 1.5x
                    risk_adjusted_alpha *= vol_adjustment
                
                # Converti da annual a daily per position value
                daily_alpha = (1 + risk_adjusted_alpha) ** (1/252) - 1
                expected_alpha = position_value * daily_alpha
                
                # Inerzia tax-friction aware
                inertia_threshold = config['settings']['inertia_threshold']
                do_nothing_score = (expected_alpha - total_cost - tax_estimate) / position_value
                
                # Se il beneficio netto supera la soglia di inerzia, allora TRADE
                # altrimenti HOLD (logica corretta: alpha >= costi → più propenso a tradare)
                recommendation = 'TRADE' if do_nothing_score >= inertia_threshold else 'HOLD'
                
                orders.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'qty': qty_target,
                    'price': current_price,
                    'reason': explain_code,
                    'expected_alpha_est': expected_alpha,
                    'fees_est': commission + slippage,
                    'tax_friction_est': tax_estimate,
                    'do_nothing_score': do_nothing_score,
                    'recommendation': recommendation
                })
                
            elif signal_state == 'RISK_OFF':
                # Vendita se posizione esistente
                if symbol in positions_dict:
                    qty = positions_dict[symbol]['qty']
                    
                    # Costi vendita
                    position_value = qty * current_price
                    commission = position_value * commission_pct
                    if position_value < 1000:
                        commission = max(5.0, commission)
                    
                    slippage_bps = max(2, current_vol * 0.5)
                    slippage = position_value * (slippage_bps / 10000)
                    
                    # Tax su gain
                    avg_price = positions_dict[symbol]['avg_price']
                    if current_price > avg_price:
                        realized_gain = (current_price - avg_price) * qty
                        tax_estimate = realized_gain * 0.26
                    else:
                        tax_estimate = 0.0
                    
                    total_cost = commission + slippage + tax_estimate
                    
                    orders.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'qty': qty,
                        'price': current_price,
                        'reason': explain_code,
                        'expected_alpha_est': 0.0,
                        'fees_est': commission + slippage,
                        'tax_friction_est': tax_estimate,
                        'do_nothing_score': 0.0,
                        'recommendation': 'TRADE'
                    })
            
            else:  # HOLD
                orders.append({
                    'symbol': symbol,
                    'action': 'HOLD',
                    'qty': 0,
                    'price': current_price,
                    'reason': explain_code,
                    'expected_alpha_est': 0.0,
                    'fees_est': 0.0,
                    'tax_friction_est': 0.0,
                    'do_nothing_score': 1.0,
                    'recommendation': 'HOLD'
                })
        
        # 5. Output ordini
        print(f" Ordini generati: {len(orders)}")
        
        orders_summary = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'orders': orders,
            'summary': {
                'total_orders': len(orders),
                'buy_orders': len([o for o in orders if o['action'] == 'BUY']),
                'sell_orders': len([o for o in orders if o['action'] == 'SELL']),
                'hold_orders': len([o for o in orders if o['action'] == 'HOLD']),
                'total_estimated_cost': sum(o['fees_est'] + o['tax_friction_est'] for o in orders),
                'total_expected_alpha': sum(o['expected_alpha_est'] for o in orders)
            }
        }
        
        # 6. Salva su file
        orders_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'orders')
        os.makedirs(orders_dir, exist_ok=True)
        orders_file = os.path.join(orders_dir, f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(orders_file, 'w') as f:
            json.dump(orders_summary, f, indent=2)
        
        print(f" Ordini salvati in: {orders_file}")
        
        # 6.1 Esegui ordini se --commit
        if not dry_run and commit:
            print("\n 🔄 COMMIT MODE - Esecuzione ordini...")
            from execute_orders import execute_orders
            success = execute_orders(orders_file=orders_file, commit=True)
            if success:
                print("✅ Ordini eseguiti con successo")
            else:
                print("❌ Errore durante l'esecuzione degli ordini")
                return False
        else:
            # Usa session manager ESISTENTE per dry-run
            session_manager = get_session_manager()
            session_manager.add_report_to_session('strategy', orders_summary, 'json')
            
            # Stampa riepilogo
            print(f"\n RIEPILOGO ORDINI:")
            for order in orders:
                emoji = "" if order['action'] == 'BUY' else "" if order['action'] == 'SELL' else ""
                print(f"{emoji} {order['symbol']}: {order['action']} {order['qty']:.0f} @ €{order['price']:.2f}")
                print(f"    {order['reason']} | Costi: €{order['fees_est'] + order['tax_friction_est']:.2f}")
                print(f"    {order['recommendation']} | Do-nothing: {order['do_nothing_score']:.3f}")
        
        return True
        
    except Exception as e:
        print(f" Errore strategy engine: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Strategy Engine ETF Italia Project')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry-run mode (default)')
    parser.add_argument('--commit', action='store_true', help='Commit changes to database')
    
    args = parser.parse_args()
    
    # Esegui strategy_engine e poi continua con la sequenza
    success = strategy_engine(dry_run=args.dry_run, commit=args.commit)
    
    if success:
        # Continua con la sequenza: backtest_runner, performance_report_generator, analyze_schema_drift
        run_sequence_from('strategy_engine')
    else:
        print("❌ Strategy engine fallito - sequenza interrotta")
        sys.exit(1)
