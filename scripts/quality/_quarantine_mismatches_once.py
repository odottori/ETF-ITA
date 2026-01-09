import duckdb
from pathlib import Path

db = Path("data/db/etf_data.duckdb")
ids = [72, 3, 4, 5, 6, 7, 14, 15, 16, 17, 18]

con = duckdb.connect(str(db))

# 1) tabella quarantena (stesso schema)
con.execute("CREATE TABLE IF NOT EXISTS fiscal_ledger_quarantine AS SELECT * FROM fiscal_ledger WHERE 1=0;")

# 2) copia in quarantena
con.execute(f"INSERT INTO fiscal_ledger_quarantine SELECT * FROM fiscal_ledger WHERE id IN ({','.join(map(str, ids))});")

# 3) delete dal ledger operativo
con.execute(f"DELETE FROM fiscal_ledger WHERE id IN ({','.join(map(str, ids))});")

remaining = con.execute("""
  SELECT COUNT(*)
  FROM fiscal_ledger fl
  LEFT JOIN market_data md ON md.symbol = fl.symbol AND md.date = fl.date
  WHERE fl.type IN ('BUY','SELL') AND md.date IS NULL
""").fetchone()[0]

max_trade = con.execute("""
  SELECT MAX(date)
  FROM fiscal_ledger
  WHERE type IN ('BUY','SELL')
""").fetchone()[0]

max_md = con.execute("SELECT MAX(date) FROM market_data").fetchone()[0]

print("Quarantined+deleted rows:", len(ids))
print("Remaining BUY/SELL mismatches:", remaining)
print("Max BUY/SELL ledger date:", max_trade)
print("Max market_data date:", max_md)

con.close()
