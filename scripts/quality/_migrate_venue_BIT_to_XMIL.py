import duckdb
from pathlib import Path

DB = Path("data/db/etf_data.duckdb")
SRC = "BIT"
DST = "XMIL"

con = duckdb.connect(str(DB))

# colonne disponibili (per essere compatibili con schemi diversi)
cols = con.execute("PRAGMA table_info('trading_calendar')").fetchall()
colnames = [c[1] for c in cols]

# costruiamo INSERT compatibile
select_expr = []
for c in colnames:
    if c == "venue":
        select_expr.append(f"'{DST}' AS venue")
    else:
        select_expr.append(c)

select_sql = ", ".join(select_expr)

# inserisci solo date non già presenti su DST
sql = f"""
INSERT INTO trading_calendar
SELECT {select_sql}
FROM trading_calendar src
WHERE src.venue = '{SRC}'
  AND NOT EXISTS (
    SELECT 1 FROM trading_calendar dst
    WHERE dst.venue = '{DST}' AND dst.date = src.date
  );
"""

before = con.execute("SELECT COUNT(*) FROM trading_calendar WHERE venue=?", [DST]).fetchone()[0]
con.execute(sql)
after = con.execute("SELECT COUNT(*) FROM trading_calendar WHERE venue=?", [DST]).fetchone()[0]

print("XMIL rows before:", before)
print("XMIL rows after :", after)
print("Inserted        :", after - before)

# sanity: counts by venue
print("\nCounts by venue:")
for row in con.execute("SELECT venue, COUNT(*) FROM trading_calendar GROUP BY venue ORDER BY venue").fetchall():
    print(" ", row)

con.close()
