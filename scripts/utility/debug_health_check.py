#!/usr/bin/env python3
import duckdb

conn = duckdb.connect('data/etf_data.duckdb')

print("=== ANALISI HEALTH CHECK DEGRADED ===")
print()

# 1. Calendar days
calendar_days = conn.execute("SELECT COUNT(*) FROM trading_calendar").fetchone()[0]
print(f"Calendar days total: {calendar_days}")

# 2. Market data days per symbol
symbols = ['CSSPX.MI', 'XS2L.MI', '^GSPC']
for symbol in symbols:
    market_days = conn.execute(f"SELECT COUNT(DISTINCT date) FROM market_data WHERE symbol='{symbol}'").fetchone()[0]
    print(f"Market data days {symbol}: {market_days}")

# 3. Date ranges
print()
print("Date ranges:")
cal_range = conn.execute("SELECT MIN(date), MAX(date) FROM trading_calendar").fetchall()
print(f"Calendar: {cal_range[0]}")

market_range = conn.execute("SELECT MIN(date), MAX(date) FROM market_data").fetchall()
print(f"Market data: {market_range[0]}")

# 4. Missing days analysis
print()
print("Missing days analysis:")
missing_query = """
SELECT 
    tc.date,
    tc.is_open,
    CASE WHEN md.date IS NOT NULL THEN 'HAS_DATA' ELSE 'NO_DATA' END as data_status
FROM trading_calendar tc
LEFT JOIN (
    SELECT DISTINCT date FROM market_data
) md ON tc.date = md.date
WHERE tc.is_open = 1
AND md.date IS NULL
ORDER BY tc.date DESC
LIMIT 10
"""

missing_days = conn.execute(missing_query).fetchall()
print("Ultimi 10 giorni trading senza dati:")
for day in missing_days:
    print(f"  {day[0]} - {day[2]}")

# 5. Count missing trading days
missing_count = conn.execute("""
SELECT COUNT(*) 
FROM trading_calendar tc
LEFT JOIN (
    SELECT DISTINCT date FROM market_data
) md ON tc.date = md.date
WHERE tc.is_open = 1
AND md.date IS NULL
""").fetchone()[0]

print(f"Total missing trading days: {missing_count}")

conn.close()
