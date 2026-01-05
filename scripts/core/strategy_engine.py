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
from implement_risk_controls import check_stop_loss_trailing_stop, calculate_portfolio_value, calculate_target_weights, calculate_current_weights

def strategy_engine(dry_run=True):
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
        
        positions_dict = {symbol: {'qty': qty, 'avg_price': avg_buy_price if avg_buy_price else 0} for symbol, qty, avg_buy_price in positions}
        
        # 3. Ottieni prezzi correnti
        print(" Caricamento prezzi correnti...")
        
        current_prices = {}
        for symbol, signal_state, risk_scalar, explain_code in current_signals:
            price_data = conn.execute("""
            SELECT adj_close, adj_close as close, 0 as volume, volatility_20d
            FROM risk_metrics 
            WHERE symbol = ? AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = ?)
            """, [symbol, symbol]).fetchone()
            
            if price_data:
                current_prices[symbol] = {
                    'adj_close': price_data[0],
                    'close': price_data[1],
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
        
        # 6. Deterministic rebalancing based on weight deviation
        rebalance_threshold = 0.05  # 5% deviation threshold
        orders = []
        
        print(" Analisi rebalancing deterministico...")
        for symbol in target_weights:
            target_weight = target_weights[symbol]
            current_weight = current_weights.get(symbol, 0.0)
            weight_deviation = abs(target_weight - current_weight)
            
            print(f"  {symbol}: target {target_weight:.3f} vs actual {current_weight:.3f} (dev: {weight_deviation:.3f})")
            
            # Force rebalance if deviation > threshold AND no conflicting signal
            if weight_deviation > rebalance_threshold:
                # Check if there's a conflicting signal for this symbol
                symbol_signal = next((s for s in current_signals if s[0] == symbol), None)
                if symbol_signal and symbol_signal[1] in ['RISK_ON', 'RISK_OFF']:
                    print(f"    ⚠️  {symbol}: Signal {symbol_signal[1]} takes precedence over rebalancing")
                    continue
                
                target_position_value = portfolio_value * target_weight
                current_position_value = portfolio_value * current_weight
                
                if symbol in current_prices:
                    current_price = current_prices[symbol]['close']
                    target_qty = target_position_value / current_price
                    current_qty = positions_dict.get(symbol, {}).get('qty', 0)
                    
                    qty_diff = target_qty - current_qty
                    
                    if abs(qty_diff) > 0:  # Only trade if meaningful difference
                        action = 'BUY' if qty_diff > 0 else 'SELL'
                        orders.append({
                            'symbol': symbol,
                            'action': action,
                            'qty': abs(qty_diff),
                            'price': current_price,
                            'reason': f'REBALANCE_{weight_deviation:.1%}_DEVIATION',
                            'expected_alpha_est': 0.0,
                            'fees_est': 0.0,  # Will be calculated below
                            'tax_friction_est': 0.0,  # Will be calculated below
                            'do_nothing_score': -1.0,  # Force rebalancing
                            'recommendation': 'TRADE'
                        })
                        print(f"    🔄 REBALANCE {symbol}: {action} {abs(qty_diff):.0f} shares")
        
        # 7. Process signals for remaining positions
        print(" Elaborazione segnali...")
        
        for symbol, signal_state, risk_scalar, explain_code in current_signals:
            if symbol not in current_prices:
                print(f"️ {symbol}: Nessun prezzo disponibile")
                continue
            
            current_price = current_prices[symbol]['close']
            current_vol = current_prices[symbol]['volatility_20d']
            
            # 4.1 Check stop-loss/trailing stop BEFORE signal processing
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
            
            # Calcola posizione target
            # portfolio_value = 20000.0  # TODO: calcolare da ledger - NOW IMPLEMENTED
            
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
                expected_alpha = position_value * 0.05  # 5% expected return
                
                # Inerzia tax-friction aware
                inertia_threshold = config['settings']['inertia_threshold']
                do_nothing_score = (expected_alpha - total_cost - tax_estimate) / position_value
                
                recommendation = 'TRADE' if do_nothing_score < 0 else 'HOLD'
                
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
        if dry_run:
            # Usa session manager ESISTENTE
            session_manager = get_session_manager()
            
            orders_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'orders')
            os.makedirs(orders_dir, exist_ok=True)
            orders_file = os.path.join(orders_dir, f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(orders_file, 'w') as f:
                json.dump(orders_summary, f, indent=2)
            
            print(f" Ordini salvati in: {orders_file}")
            
            # Salva nella STESSA sessione
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
    
    success = strategy_engine(dry_run=args.dry_run)
    sys.exit(0 if success else 1)
