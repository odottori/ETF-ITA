#!/usr/bin/env python3
"""
Strategy Engine V2 - ETF Italia Project v10
Implementa holding period dinamico + portfolio construction
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.path_manager import get_path_manager
from strategy.portfolio_construction import (
    calculate_expected_holding_days,
    calculate_candidate_score,
    rank_candidates,
    get_current_positions,
    calculate_available_cash,
    filter_by_constraints,
    should_extend_holding,
    calculate_qty,
    get_positions_for_review
)


def generate_orders_with_holding_period(
    conn,
    config: dict,
    current_date: datetime.date = None,
    run_type: str = 'BACKTEST',
    run_id: str = None,
    underlying_map: dict = None
) -> dict:
    """
    Genera ordini con logica holding period dinamico + portfolio construction
    Design v2.0: Workflow TWO-PASS (Exit → Cash Update → Entry)
    
    PASS 1: Exit/SELL (MANDATORY first)
    - MANDATORY exits: RISK_OFF / stop-loss / guardrails
    - Planned exits: today >= expected_exit_date
    - Pre-trade checks: oversell, qty > 0
    - Scrivi orders_plan (SELL) con decision_path e reason_code
    
    CASH UPDATE (simulato):
    - Simula cash post-sell per decidere entry con cash realistico
    
    PASS 2: Entry/Rebalance (OPPORTUNISTIC + FORCED):
    - Genera candidati entry/rebalance
    - Calcola candidate_score (0..1) e applica filtri
    - Applica constraints hard: max positions, cash reserve, overlap
    - Alloca capitale deterministico + rounding
    - Scrivi orders_plan (BUY/REBALANCE) e reject_reason
    
    Args:
        conn: DuckDB connection
        config: Config dict
        current_date: Data corrente (default: ultima data disponibile)
        run_type: BACKTEST o PRODUCTION
        run_id: UUID run (generato se None)
        underlying_map: Dict {symbol: underlying} per overlap check
        
    Returns:
        Dict con orders, rejects, metrics
    """
    
    import uuid
    import hashlib
    
    if current_date is None:
        current_date = conn.execute("SELECT MAX(date) FROM signals").fetchone()[0]
    
    if run_id is None:
        run_id = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    if underlying_map is None:
        # Default: ogni simbolo è il proprio underlying (no overlap)
        underlying_map = {}
    
    # Config snapshot hash per audit
    config_json = json.dumps(config, sort_keys=True)
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
    
    print(f"\n{'=' * 80}")
    print(f"STRATEGY ENGINE V2 - TWO-PASS Workflow (Design v2.0)")
    print(f"{'=' * 80}")
    print(f"Run ID: {run_id}")
    print(f"Data: {current_date}")
    print(f"Run type: {run_type}")
    print(f"Config hash: {config_hash}\n")
    
    orders_sell = []
    orders_buy = []
    rejects = []
    
    # ========================================================================
    # PASS 1: EXIT/SELL (MANDATORY FIRST)
    # ========================================================================
    print("🔴 PASS 1: EXIT/SELL (MANDATORY FIRST)")
    print("-" * 80)
    
    signals_query = """
    SELECT 
        s.symbol,
        s.signal_state,
        s.risk_scalar,
        s.explain_code,
        rm.volatility_20d,
        rm.close,
        rm.adj_close
    FROM signals s
    JOIN risk_metrics rm ON s.symbol = rm.symbol AND s.date = rm.date
    WHERE s.date = ?
    ORDER BY s.symbol
    """
    
    signals_data = {}
    candidates = []
    
    for row in conn.execute(signals_query, [current_date]).fetchall():
        symbol, signal_state, risk_scalar, explain_code, volatility, close, adj_close = row
        
        # Calcola momentum_score (semplificato: basato su risk_scalar)
        momentum_score = risk_scalar * 0.8  # Placeholder, da migliorare con SMA/trend
        
        # TER e slippage (da config per simbolo)
        ter = 0.001  # Default 0.1%
        slippage_bps = 5  # Default 5bps
        
        signals_data[symbol] = {
            'signal_state': signal_state,
            'risk_scalar': risk_scalar,
            'explain_code': explain_code,
            'volatility': volatility if volatility else 0.15,
            'close': close,
            'adj_close': adj_close,
            'momentum_score': momentum_score,
            'ter': ter,
            'slippage_bps': slippage_bps
        }
    
    # Ottieni posizioni correnti
    current_positions = get_current_positions(conn, run_type)
    print(f"Posizioni aperte: {len(current_positions)}")
    for symbol, pos in current_positions.items():
        days_held = (current_date - pos['entry_date']).days
        print(f"  {symbol:10} → qty: {pos['qty']:.0f}, days_held: {days_held}, expected: {pos['expected_holding_days']}")
    
    # PASS 1A: MANDATORY exits (RISK_OFF, stop-loss, take-profit, trailing stop, guardrails)
    print("\n1A. MANDATORY exits (RISK_OFF, stop-loss, take-profit, guardrails)")
    
    # Parametri da config (calibrati per trend graduali)
    stop_loss_pct = -0.08  # -8% (più stretto per protezione)
    take_profit_pct = 0.05  # +5% (più basso per catturare gain graduali)
    trailing_stop_activation = 0.03  # Attiva trailing da +3%
    trailing_stop_pct = -0.03  # -3% da peak (più stretto)
    vol_breaker = config.get('risk_management', {}).get('volatility_breaker', 0.20)
    
    for symbol, pos in current_positions.items():
        signal = signals_data.get(symbol)
        if not signal:
            continue
        
        qty = pos['qty']
        price = signal['close']
        entry_price = pos.get('entry_price', price)
        
        # Calcola P&L
        pnl_pct = (price - entry_price) / entry_price if entry_price > 0 else 0
        
        # MANDATORY 1: RISK_OFF
        if signal['signal_state'] == 'RISK_OFF':
            orders_sell.append({
                'symbol': symbol,
                'action': 'SELL',
                'qty': qty,
                'price': price,
                'decision_path': 'MANDATORY_RISK_OFF',
                'reason_code': 'RISK_OFF_TRIGGER',
                'status': 'TRADE'
            })
            print(f"  ✅ SELL {symbol}: RISK_OFF → {qty:.0f} @ €{price:.2f} (P&L: {pnl_pct*100:+.1f}%)")
            continue
        
        # MANDATORY 2: Stop-Loss
        if pnl_pct <= stop_loss_pct:
            orders_sell.append({
                'symbol': symbol,
                'action': 'SELL',
                'qty': qty,
                'price': price,
                'decision_path': 'MANDATORY_STOP_LOSS',
                'reason_code': 'STOP_LOSS_HIT',
                'status': 'TRADE'
            })
            print(f"  🛑 SELL {symbol}: STOP-LOSS → {qty:.0f} @ €{price:.2f} (P&L: {pnl_pct*100:+.1f}%)")
            continue
        
        # MANDATORY 3: Take-Profit (opportunistico ma prioritario)
        if pnl_pct >= take_profit_pct:
            orders_sell.append({
                'symbol': symbol,
                'action': 'SELL',
                'qty': qty,
                'price': price,
                'decision_path': 'OPPORTUNISTIC_TAKE_PROFIT',
                'reason_code': 'TAKE_PROFIT_TARGET',
                'status': 'TRADE'
            })
            print(f"  💰 SELL {symbol}: TAKE-PROFIT → {qty:.0f} @ €{price:.2f} (P&L: {pnl_pct*100:+.1f}%)")
            continue
        
        # MANDATORY 4: Trailing Stop (calcola peak da entry)
        # Nota: richiede tracking peak price, per ora usa entry_price come baseline
        peak_price = max(entry_price * (1 + trailing_stop_activation), price)  # Peak da activation threshold
        drawdown_from_peak = (price - peak_price) / peak_price if peak_price > 0 else 0
        
        if pnl_pct > trailing_stop_activation and drawdown_from_peak <= trailing_stop_pct:
            orders_sell.append({
                'symbol': symbol,
                'action': 'SELL',
                'qty': qty,
                'price': price,
                'decision_path': 'MANDATORY_TRAILING_STOP',
                'reason_code': 'TRAILING_STOP_BREACH',
                'status': 'TRADE'
            })
            print(f"  📉 SELL {symbol}: TRAILING-STOP → {qty:.0f} @ €{price:.2f} (P&L: {pnl_pct*100:+.1f}%)")
            continue
        
        # MANDATORY 5: Guardrails - Volatility Breaker
        volatility = signal.get('volatility', 0.15)
        if volatility >= vol_breaker:
            orders_sell.append({
                'symbol': symbol,
                'action': 'SELL',
                'qty': qty,
                'price': price,
                'decision_path': 'MANDATORY_GUARDRAIL',
                'reason_code': 'VOLATILITY_BREAKER',
                'status': 'TRADE'
            })
            print(f"  ⚠️  SELL {symbol}: VOLATILITY BREAKER → {qty:.0f} @ €{price:.2f} (vol: {volatility*100:.1f}%)")
            continue
    
    # PASS 1B: Planned exits (holding scaduto)
    print("\n1B. Planned exits (holding scaduto)")
    positions_for_review = get_positions_for_review(conn, current_date, run_type)
    
    for position in positions_for_review:
        symbol = position['symbol']
        qty = position['qty']
        
        # Skip se già venduto in MANDATORY
        if any(o['symbol'] == symbol for o in orders_sell):
            continue
        
        signal = signals_data.get(symbol)
        if not signal:
            continue
        
        # Decide se estendere o uscire
        should_extend, new_holding_days = should_extend_holding(
            position,
            signal,
            current_date,
            config
        )
        
        if should_extend:
            print(f"  🔄 {symbol}: ESTENDI holding → {new_holding_days}d")
            # TODO: Scrivere position_events con HOLDING_EXTENDED
        else:
            price = signal['close']
            orders_sell.append({
                'symbol': symbol,
                'action': 'SELL',
                'qty': qty,
                'price': price,
                'decision_path': 'EXIT_PLANNED',
                'reason_code': 'EXIT_DATE_REACHED',
                'status': 'TRADE'
            })
            print(f"  ✅ SELL {symbol}: EXIT pianificato → {qty:.0f} @ €{price:.2f}")
    
    print(f"\nTotale SELL proposti: {len(orders_sell)}")
    print()
    
    # ========================================================================
    # CASH UPDATE (SIMULATO)
    # ========================================================================
    print("💰 CASH UPDATE (simulato post-sell)")
    print("-" * 80)
    
    # Calcola portfolio value
    portfolio_value_query = """
    WITH positions AS (
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty
        FROM fiscal_ledger
        WHERE run_type = ?
          AND type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) > 0
    ),
    position_values AS (
        SELECT 
            p.symbol,
            p.qty,
            md.close,
            p.qty * md.close as market_value
        FROM positions p
        JOIN market_data md ON p.symbol = md.symbol
        WHERE md.date = (SELECT MAX(date) FROM market_data WHERE symbol = p.symbol)
    ),
    cash_balance AS (
        SELECT COALESCE(SUM(CASE 
            WHEN type = 'DEPOSIT' THEN qty * price
            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
            WHEN type = 'BUY' THEN -(qty * price + fees)
            WHEN type = 'INTEREST' THEN qty
            ELSE 0 
        END), 0) as cash
        FROM fiscal_ledger
        WHERE run_type = ?
    )
    SELECT 
        COALESCE(SUM(pv.market_value), 0) + (SELECT cash FROM cash_balance) as total_value,
        (SELECT cash FROM cash_balance) as cash
    FROM position_values pv
    """
    
    result = conn.execute(portfolio_value_query, [run_type, run_type]).fetchone()
    portfolio_value = result[0] if result[0] else config['settings']['start_capital']
    cash_balance_pre = result[1] if result[1] else config['settings']['start_capital']
    
    # Simula cash post-sell
    exec_cfg = config.get('execution', {})
    exec_mode = exec_cfg.get('execution_price_mode', 'CLOSE_SAME_DAY_SLIPPAGE')
    slippage_default = exec_cfg.get('slippage_bps_default', 5)
    
    cash_from_sells = 0.0
    for sell_order in orders_sell:
        price = sell_order['price']
        qty = sell_order['qty']
        # Execution price con slippage (SELL: -slippage)
        exec_price = price * (1 - slippage_default / 10000)
        cash_from_sells += qty * exec_price
    
    cash_balance_post = cash_balance_pre + cash_from_sells
    
    print(f"Cash balance PRE-sell: €{cash_balance_pre:,.2f}")
    print(f"Cash from sells: €{cash_from_sells:,.2f}")
    print(f"Cash balance POST-sell: €{cash_balance_post:,.2f}")
    
    # Calcola cash disponibile (con cash post-sell)
    min_cash_reserve_pct = config.get('portfolio_construction', {}).get('min_cash_reserve_pct', 0.10)
    min_reserve = portfolio_value * min_cash_reserve_pct
    available_cash = max(0.0, cash_balance_post - min_reserve)
    
    print(f"Cash reserve (10%): €{min_reserve:,.2f}")
    print(f"Cash disponibile per entry: €{available_cash:,.2f}")
    print()
    
    # ========================================================================
    # PASS 2: ENTRY/REBALANCE (OPPORTUNISTIC + FORCED)
    # ========================================================================
    print("🟢 PASS 2: ENTRY/REBALANCE (OPPORTUNISTIC + FORCED)")
    print("-" * 80)
    
    # Identifica candidati RISK_ON
    candidates = [s for s, data in signals_data.items() if data['signal_state'] == 'RISK_ON']
    print(f"Candidati RISK_ON: {len(candidates)}")
    if candidates:
        print(f"  {', '.join(candidates)}")
    
    # Ranking candidati
    print("\n2A. Ranking candidati per score")
    ranked_candidates = rank_candidates(
        candidates,
        signals_data,
        current_positions,
        underlying_map,
        config
    )
    
    if ranked_candidates:
        for i, (symbol, score) in enumerate(ranked_candidates[:5], 1):
            print(f"  {i}. {symbol:10} → score: {score:.3f}")
    
    # Filtra per constraints
    print("\n2B. Filtra per constraints")
    final_candidates = filter_by_constraints(
        ranked_candidates,
        current_positions,
        available_cash,
        current_date,
        config
    )
    
    print(f"Candidati dopo filtri: {len(final_candidates)}")
    
    # Allocazione capitale
    print("\n2C. Allocazione capitale")
    
    min_trade_value = config.get('portfolio_construction', {}).get('min_trade_value', 2000)
    max_entries_per_day = exec_cfg.get('max_entries_per_day', 1)
    entries_today = 0
    
    for symbol, score in final_candidates:
        if available_cash < min_trade_value:
            rejects.append({
                'symbol': symbol,
                'reason': 'CASH_INSUFFICIENT',
                'available_cash': available_cash,
                'min_required': min_trade_value
            })
            print(f"  ❌ {symbol}: REJECT (cash €{available_cash:.0f} < min €{min_trade_value:.0f})")
            continue
        
        if entries_today >= max_entries_per_day:
            rejects.append({
                'symbol': symbol,
                'reason': 'MAX_ENTRIES_PER_DAY',
                'max_allowed': max_entries_per_day
            })
            print(f"  ❌ {symbol}: REJECT (max {max_entries_per_day} entry/day)")
            continue
        
        signal = signals_data[symbol]
        price = signal['close']
        risk_scalar = signal['risk_scalar']
        volatility = signal['volatility']
        momentum_score = signal['momentum_score']
        signal_state = signal['signal_state']
        
        # Calcola holding period dinamico
        expected_holding_days = calculate_expected_holding_days(
            risk_scalar,
            volatility,
            momentum_score,
            signal_state,
            config
        )
        
        expected_exit_date = current_date + timedelta(days=expected_holding_days)
        
        # Calcola qty
        qty = calculate_qty(
            symbol,
            price,
            available_cash,
            portfolio_value,
            risk_scalar,
            config
        )
        
        if qty > 0:
            # Execution price con slippage (BUY: +slippage)
            exec_price = price * (1 + slippage_default / 10000)
            order_value = qty * exec_price
            
            orders_buy.append({
                'symbol': symbol,
                'action': 'BUY',
                'qty': qty,
                'price': price,
                'exec_price': exec_price,
                'decision_path': 'OPPORTUNISTIC_ENTRY',
                'reason_code': 'ENTRY_SCORE_PASS',
                'entry_score': score,
                'expected_holding_days': expected_holding_days,
                'expected_exit_date': expected_exit_date,
                'status': 'TRADE'
            })
            
            available_cash -= order_value
            entries_today += 1
            
            print(f"  ✅ BUY {symbol}: {qty} @ €{price:.2f} (score: {score:.3f}, holding: {expected_holding_days}d)")
        else:
            rejects.append({
                'symbol': symbol,
                'reason': 'QTY_ZERO',
                'price': price,
                'available_cash': available_cash
            })
            print(f"  ❌ {symbol}: REJECT (qty=0, price €{price:.2f} troppo alto)")
    
    print()
    
    
    # ========================================================================
    # RIEPILOGO & METRICS
    # ========================================================================
    print("=" * 80)
    print("RIEPILOGO")
    print("=" * 80)
    
    all_orders = orders_sell + orders_buy
    proposed_orders = len(all_orders)
    executed_orders = len([o for o in all_orders if o['status'] == 'TRADE'])
    rejected_orders = len(rejects)
    
    print(f"SELL: {len(orders_sell)}")
    for order in orders_sell:
        print(f"  {order['symbol']:10} → {order['qty']:.0f} @ €{order['price']:.2f} ({order['decision_path']})")
    
    print(f"\nBUY: {len(orders_buy)}")
    for order in orders_buy:
        print(f"  {order['symbol']:10} → {order['qty']:.0f} @ €{order['price']:.2f} (holding: {order['expected_holding_days']}d)")
    
    print(f"\nREJECTS: {len(rejects)}")
    for reject in rejects[:5]:  # Max 5 per brevità
        print(f"  {reject['symbol']:10} → {reject['reason']}")
    
    # Metriche
    order_execution_rate = executed_orders / proposed_orders if proposed_orders > 0 else 0.0
    reject_rate = rejected_orders / (proposed_orders + rejected_orders) if (proposed_orders + rejected_orders) > 0 else 0.0
    
    print(f"\nMETRICS:")
    print(f"  Proposed orders: {proposed_orders}")
    print(f"  Executed orders: {executed_orders}")
    print(f"  Rejected orders: {rejected_orders}")
    print(f"  Order execution rate: {order_execution_rate:.1%}")
    print(f"  Reject rate: {reject_rate:.1%}")
    print()
    
    return {
        'run_id': run_id,
        'date': current_date,
        'orders_sell': orders_sell,
        'orders_buy': orders_buy,
        'rejects': rejects,
        'metrics': {
            'proposed_orders': proposed_orders,
            'executed_orders': executed_orders,
            'rejected_orders': rejected_orders,
            'order_execution_rate': order_execution_rate,
            'reject_rate': reject_rate
        },
        'config_hash': config_hash
    }


def main():
    """Entry point per test standalone"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Strategy Engine V2 con Holding Period')
    parser.add_argument('--date', help='Data target (YYYY-MM-DD)')
    parser.add_argument('--run-type', default='BACKTEST', choices=['BACKTEST', 'PRODUCTION'])
    parser.add_argument('--dry-run', action='store_true', default=True)
    
    args = parser.parse_args()
    
    pm = get_path_manager()
    db_path = pm.db_path
    config_path = pm.etf_universe_path
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(str(db_path))
    
    try:
        current_date = None
        if args.date:
            current_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        
        orders = generate_orders_with_holding_period(
            conn,
            config,
            current_date,
            args.run_type,
            args.dry_run
        )
        
        print(f"\n✅ Generati {len(orders)} ordini")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
