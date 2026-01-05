#!/usr/bin/env python3
import duckdb

conn = duckdb.connect('data/etf_data.duckdb')

# Test current signals query
current_signals = conn.execute("""
SELECT symbol, signal_state, risk_scalar, explain_code
FROM signals 
WHERE date = (SELECT MAX(date) FROM signals)
ORDER BY symbol
""").fetchall()

print(f"Current signals found: {len(current_signals)}")
for signal in current_signals:
    print(f"  {signal} (len: {len(signal)})")

conn.close()
