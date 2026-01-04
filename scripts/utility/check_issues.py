import duckdb
conn = duckdb.connect('data/etf_data.duckdb')
issues = conn.execute('SELECT * FROM health_issues WHERE issue_type IN ("ZOMBIE_PRICE", "LARGE_GAP") ORDER BY symbol, date').fetchall()
print('🔍 INTEGRITY ISSUES DETTAGLI:')
for issue in issues:
    print(f'• {issue[0]}: {issue[1]} - {issue[2]}')
conn.close()
