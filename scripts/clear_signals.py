import duckdb
conn = duckdb.connect('data/etf_data.duckdb')
conn.execute("DELETE FROM signals WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')")
conn.commit()
conn.close()
