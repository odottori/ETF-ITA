#!/usr/bin/env python3
import duckdb

conn = duckdb.connect('data/etf_data.duckdb')

# Check existing signals
result = conn.execute("SELECT COUNT(*) FROM signals WHERE symbol = 'CSSPX.MI' AND date = '2026-01-02'").fetchone()
print(f'Signals esistenti per CSSPX.MI 2026-01-02: {result[0]}')

result = conn.execute("SELECT MAX(date) FROM signals WHERE symbol = 'CSSPX.MI'").fetchone()
print(f'Ultima data signals CSSPX.MI: {result[0]}')

result = conn.execute('SELECT COUNT(*) FROM signals').fetchone()
print(f'Total signals in database: {result[0]}')

conn.close()
