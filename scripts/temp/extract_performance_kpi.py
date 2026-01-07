"""
Extract current performance KPI from DB for critical analysis.
Temporary script for performance assessment v10.7.8.
"""
import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "etf_data.duckdb"

def main():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    
    print("=" * 80)
    print("PERFORMANCE KPI EXTRACTION - ETF-ITA v10.7.8")
    print("=" * 80)
    
    # 1. DB Status
    print("\n### DB STATUS ###")
    sessions = conn.execute("SELECT COUNT(DISTINCT session_id) as total_sessions FROM proposed_orders").fetchdf()
    print(f"Total sessions: {sessions['total_sessions'].iloc[0]}")
    
    latest_session = conn.execute("""
        SELECT session_id, COUNT(*) as orders, MIN(created_at) as first_order 
        FROM proposed_orders 
        GROUP BY session_id 
        ORDER BY first_order DESC 
        LIMIT 1
    """).fetchdf()
    print(f"\nLatest session: {latest_session['session_id'].iloc[0]}")
    print(f"Orders in session: {latest_session['orders'].iloc[0]}")
    print(f"Session date: {latest_session['first_order'].iloc[0]}")
    
    # 2. Portfolio Overview
    print("\n### PORTFOLIO OVERVIEW ###")
    portfolio = conn.execute("SELECT * FROM portfolio_summary ORDER BY market_value DESC").fetchdf()
    if len(portfolio) > 0:
        print(portfolio.to_string(index=False))
        print(f"\nTotal positions: {len(portfolio)}")
        print(f"Total market value: €{portfolio['market_value'].sum():,.2f}")
    else:
        print("No positions in portfolio")
    
    # 3. Cash Position
    print("\n### CASH POSITION ###")
    cash = conn.execute("""
        SELECT cash_balance, total_invested, total_market_value, 
               (total_market_value - total_invested) as unrealized_pnl,
               date
        FROM cash_ledger 
        ORDER BY date DESC 
        LIMIT 1
    """).fetchdf()
    if len(cash) > 0:
        print(f"Date: {cash['date'].iloc[0]}")
        print(f"Cash balance: €{cash['cash_balance'].iloc[0]:,.2f}")
        print(f"Total invested: €{cash['total_invested'].iloc[0]:,.2f}")
        print(f"Total market value: €{cash['total_market_value'].iloc[0]:,.2f}")
        print(f"Unrealized P&L: €{cash['unrealized_pnl'].iloc[0]:,.2f}")
        
        total_equity = cash['cash_balance'].iloc[0] + cash['total_market_value'].iloc[0]
        print(f"Total equity: €{total_equity:,.2f}")
    else:
        print("No cash ledger data")
    
    # 4. Equity Curve
    print("\n### EQUITY CURVE (last 20 days) ###")
    equity_curve = conn.execute("""
        SELECT date, 
               cash_balance + total_market_value as total_equity,
               total_market_value,
               cash_balance
        FROM cash_ledger 
        ORDER BY date DESC 
        LIMIT 20
    """).fetchdf()
    if len(equity_curve) > 0:
        print(equity_curve.to_string(index=False))
    else:
        print("No equity curve data")
    
    # 5. Trade Statistics
    print("\n### TRADE STATISTICS ###")
    trades = conn.execute("""
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buys,
            SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sells,
            SUM(total_cost) as total_volume
        FROM ledger
        WHERE action IN ('BUY', 'SELL')
    """).fetchdf()
    print(trades.to_string(index=False))
    
    # 6. Realized P&L
    print("\n### REALIZED P&L ###")
    realized_pnl = conn.execute("""
        SELECT 
            SUM(realized_gain_loss) as total_realized_pnl,
            SUM(CASE WHEN realized_gain_loss > 0 THEN realized_gain_loss ELSE 0 END) as total_gains,
            SUM(CASE WHEN realized_gain_loss < 0 THEN realized_gain_loss ELSE 0 END) as total_losses,
            COUNT(CASE WHEN realized_gain_loss > 0 THEN 1 END) as winning_trades,
            COUNT(CASE WHEN realized_gain_loss < 0 THEN 1 END) as losing_trades
        FROM ledger
        WHERE action = 'SELL' AND realized_gain_loss IS NOT NULL
    """).fetchdf()
    if len(realized_pnl) > 0 and realized_pnl['total_realized_pnl'].iloc[0] is not None:
        print(f"Total realized P&L: €{realized_pnl['total_realized_pnl'].iloc[0]:,.2f}")
        print(f"Total gains: €{realized_pnl['total_gains'].iloc[0]:,.2f}")
        print(f"Total losses: €{realized_pnl['total_losses'].iloc[0]:,.2f}")
        print(f"Winning trades: {realized_pnl['winning_trades'].iloc[0]}")
        print(f"Losing trades: {realized_pnl['losing_trades'].iloc[0]}")
        
        total_trades = realized_pnl['winning_trades'].iloc[0] + realized_pnl['losing_trades'].iloc[0]
        if total_trades > 0:
            win_rate = realized_pnl['winning_trades'].iloc[0] / total_trades * 100
            print(f"Win rate: {win_rate:.1f}%")
    else:
        print("No realized P&L data")
    
    # 7. Latest Proposed Orders
    print("\n### LATEST PROPOSED ORDERS (last session) ###")
    latest_orders = conn.execute("""
        SELECT symbol, action, quantity, reason, momentum_score, trade_score
        FROM proposed_orders
        WHERE session_id = (SELECT session_id FROM proposed_orders ORDER BY created_at DESC LIMIT 1)
        ORDER BY created_at
    """).fetchdf()
    if len(latest_orders) > 0:
        print(latest_orders.to_string(index=False))
    else:
        print("No proposed orders in latest session")
    
    # 8. Risk Metrics Summary
    print("\n### RISK METRICS SUMMARY (current positions) ###")
    risk_summary = conn.execute("""
        SELECT 
            ps.symbol,
            rm.volatility_20d,
            rm.max_drawdown_20d,
            rm.risk_scalar,
            ps.quantity,
            ps.market_value
        FROM portfolio_summary ps
        JOIN risk_metrics rm ON ps.symbol = rm.symbol
        WHERE rm.date = (SELECT MAX(date) FROM risk_metrics)
        ORDER BY ps.market_value DESC
    """).fetchdf()
    if len(risk_summary) > 0:
        print(risk_summary.to_string(index=False))
    else:
        print("No risk metrics data")
    
    conn.close()
    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    main()
