#!/usr/bin/env python3
import duckdb

conn = duckdb.connect('data/etf_data.duckdb')

# Test price query for CSSPX.MI
price_data = conn.execute("""
SELECT adj_close, close, volume, volatility_20d
FROM risk_metrics 
WHERE symbol = ? AND date = (SELECT MAX(date) FROM risk_metrics WHERE symbol = ?)
""", ['CSSPX.MI', 'CSSPX.MI']).fetchone()

print(f"Price data for CSSPX.MI: {price_data}")
print(f"Length: {len(price_data) if price_data else 0}")

conn.close()
