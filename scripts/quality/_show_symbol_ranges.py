import duckdb
from pathlib import Path

db = Path("data/db/etf_data.duckdb")
symbols = ["CSSPX.MI","EIMI.MI","SGLD.MI","AGGH.MI","XS2L.MI"]

con = duckdb.connect(str(db))

q = """
SELECT symbol,
       MIN(date) AS first_date,
       MAX(date) AS last_date,
       COUNT(*)  AS n
FROM market_data
WHERE symbol IN ({})
GROUP BY symbol
ORDER BY first_date;
""".format(",".join([f"'{s}'" for s in symbols]))

rows = con.execute(q).fetchall()

print("\nSYMBOL DATE RANGES")
print("==========================================")
for r in rows:
    print(f"{r[0]:10s} first={r[1]} last={r[2]} n={r[3]}")
print("==========================================\n")

con.close()
