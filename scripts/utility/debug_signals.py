#!/usr/bin/env python3
import duckdb

conn = duckdb.connect('data/etf_data.duckdb')

# Check what exists for CSSPX.MI 2026-01-02
result = conn.execute("SELECT * FROM signals WHERE symbol = 'CSSPX.MI' AND date = '2026-01-02'").fetchall()
print(f"Signals esistenti per CSSPX.MI 2026-01-02: {len(result)}")
for row in result:
    print(f"  {row}")

# Check if there are multiple entries
result = conn.execute("SELECT COUNT(*) FROM signals WHERE symbol = 'CSSPX.MI' AND date = '2026-01-02'").fetchone()
print(f"Count: {result[0]}")

conn.close()
