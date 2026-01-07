"""
Analisi critica anomalie backtest per identificare root cause.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from utils.path_manager import get_path_manager

pm = get_path_manager()
conn = duckdb.connect(str(pm.db_path), read_only=True)

print("=" * 80)
print("ANALISI CRITICA ANOMALIE BACKTEST")
print("=" * 80)

# 1. Ordini eseguiti
print("\n### ORDINI ESEGUITI (BACKTEST) ###")
orders = conn.execute("""
    SELECT date, symbol, type, qty, price, fees, tax_paid, notes
    FROM fiscal_ledger
    WHERE run_type = 'BACKTEST'
    AND type IN ('BUY', 'SELL')
    ORDER BY date
""").fetchdf()
print(f"Total orders: {len(orders)}")
print(orders.to_string(index=False))

# 2. Equity curve giornaliera
print("\n### EQUITY CURVE (primi 20 giorni) ###")
equity = conn.execute("""
    WITH daily_cash AS (
        SELECT 
            date,
            SUM(CASE 
                WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
                WHEN type = 'SELL' THEN qty * price - fees - tax_paid
                WHEN type = 'BUY' THEN -(qty * price + fees)
                ELSE 0 
            END) OVER (ORDER BY date) as cumulative_cash
        FROM fiscal_ledger
        WHERE run_type = 'BACKTEST'
    ),
    daily_positions AS (
        SELECT 
            fl.date,
            fl.symbol,
            SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) OVER (PARTITION BY fl.symbol ORDER BY fl.date) as position,
            md.close
        FROM fiscal_ledger fl
        JOIN market_data md ON fl.symbol = md.symbol AND fl.date <= md.date
        WHERE fl.run_type = 'BACKTEST'
        AND fl.type IN ('BUY', 'SELL')
    )
    SELECT 
        dc.date,
        dc.cumulative_cash,
        COALESCE(SUM(dp.position * dp.close), 0) as market_value,
        dc.cumulative_cash + COALESCE(SUM(dp.position * dp.close), 0) as total_equity
    FROM daily_cash dc
    LEFT JOIN daily_positions dp ON dc.date = dp.date
    GROUP BY dc.date, dc.cumulative_cash
    ORDER BY dc.date
    LIMIT 20
""").fetchdf()
print(equity.to_string(index=False))

# 3. Posizioni finali
print("\n### POSIZIONI FINALI ###")
positions = conn.execute("""
    SELECT 
        symbol,
        SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_position
    FROM fiscal_ledger
    WHERE run_type = 'BACKTEST'
    AND type IN ('BUY', 'SELL')
    GROUP BY symbol
    HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) > 0
""").fetchdf()
print(positions.to_string(index=False))

# 4. Cash finale
print("\n### CASH FINALE ###")
cash = conn.execute("""
    SELECT 
        SUM(CASE 
            WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
            WHEN type = 'BUY' THEN -(qty * price + fees)
            ELSE 0 
        END) as final_cash
    FROM fiscal_ledger
    WHERE run_type = 'BACKTEST'
""").fetchdf()
print(f"Final cash: €{cash['final_cash'].iloc[0]:,.2f}")

# 5. Segnali generati vs ordini eseguiti
print("\n### SEGNALI VS ORDINI ###")
signals_stats = conn.execute("""
    SELECT 
        signal_state,
        COUNT(*) as total_signals,
        COUNT(DISTINCT date) as trading_days
    FROM signals
    WHERE date BETWEEN '2025-01-05' AND '2026-01-05'
    GROUP BY signal_state
    ORDER BY total_signals DESC
""").fetchdf()
print(signals_stats.to_string(index=False))

print(f"\nOrders executed: {len(orders)}")
print(f"Trading days with signals: {signals_stats['trading_days'].sum()}")
print(f"Execution rate: {len(orders) / signals_stats['trading_days'].sum() * 100:.1f}%")

# 6. Verifica portfolio_overview
print("\n### PORTFOLIO OVERVIEW (sample) ###")
po = conn.execute("""
    SELECT * FROM portfolio_overview
    ORDER BY date DESC
    LIMIT 10
""").fetchdf()
print(po.to_string(index=False))

conn.close()
print("\n" + "=" * 80)
