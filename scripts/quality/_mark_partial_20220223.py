import duckdb

DB="data/db/etf_data.duckdb"
VENUE="BIT"
DAY="2022-02-23"
FLAG="DATA_PARTIAL"
REASON="missing market_data for CSSPX.MI"

con = duckdb.connect(DB)

cols = [r[1] for r in con.execute("PRAGMA table_info('trading_calendar')").fetchall()]

sets = []
if "quality_flag" in cols: sets.append("quality_flag = ?")
if "reason" in cols: sets.append("reason = ?")

if not sets:
    print("No quality columns found in trading_calendar; nothing to update.")
else:
    sql = f"UPDATE trading_calendar SET {', '.join(sets)} WHERE venue=? AND date=?"
    params = []
    if "quality_flag" in cols: params.append(FLAG)
    if "reason" in cols: params.append(REASON)
    params += [VENUE, DAY]
    con.execute(sql, params)
    print("Updated trading_calendar for", DAY, "venue", VENUE, "->", FLAG)

con.close()
