#!/usr/bin/env python3
import duckdb

conn = duckdb.connect('data/etf_data.duckdb')

# Test positions query
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

print(f"Positions found: {len(positions)}")
for pos in positions:
    print(f"  {pos}")

conn.close()
