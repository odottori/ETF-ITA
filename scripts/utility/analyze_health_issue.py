#!/usr/bin/env python3
import duckdb
from datetime import datetime

conn = duckdb.connect('data/etf_data.duckdb')

print("=== ANALISI HEALTH CHECK - PROBLEMA IDENTIFICATO ===")
print()

# 1. Data corrente
today = datetime.now().date()
print(f"Data corrente: {today}")

# 2. Ultimo giorno con dati market
last_market_day = conn.execute("SELECT MAX(date) FROM market_data").fetchone()[0]
print(f"Ultimo giorno con dati market: {last_market_day}")

# 3. Giorni futuri nel calendar
future_days_query = """
SELECT COUNT(*) 
FROM trading_calendar 
WHERE date > ? 
AND is_open = 1
"""
future_days = conn.execute(future_days_query, [last_market_day]).fetchone()[0]
print(f"Giorni trading futuri (dopo ultimo dato): {future_days}")

# 4. Giorni mancanti reali (fino a oggi)
real_missing_query = """
SELECT COUNT(*) 
FROM trading_calendar tc
LEFT JOIN (
    SELECT DISTINCT date FROM market_data
) md ON tc.date = md.date
WHERE tc.is_open = 1
AND tc.date <= ?
AND tc.date >= '2020-01-01'
AND md.date IS NULL
"""
real_missing = conn.execute(real_missing_query, [today]).fetchone()[0]
print(f"Giorni mancanti reali (fino a oggi): {real_missing}")

# 5. Dettagli giorni mancanti recenti
recent_missing = conn.execute("""
SELECT tc.date 
FROM trading_calendar tc
LEFT JOIN (
    SELECT DISTINCT date FROM market_data
) md ON tc.date = md.date
WHERE tc.is_open = 1
AND tc.date <= ?
AND tc.date >= ?
AND md.date IS NULL
ORDER BY tc.date DESC
LIMIT 5
""", [today, last_market_day]).fetchall()

print()
print("Giorni mancanti recenti (dopo ultimo dato):")
for day in recent_missing:
    print(f"  {day[0]}")

conn.close()

print()
print("=== CONCLUSIONE ===")
print("Il health check conta 260 giorni mancanti perché:")
print("1. Il calendar va fino al 31-12-2026")
print("2. I dati market sono fermi al 02-01-2026") 
print("3. Tutti i giorni trading tra 03-01-2026 e 31-12-2026 sono contati come 'mancanti'")
print("4. Questo è normale - sono giorni futuri!")
print()
print("SOLUZIONE: Modificare health check per contare solo giorni fino a data odierna")
