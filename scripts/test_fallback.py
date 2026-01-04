#!/usr/bin/env python3
"""
Test Fallback - Cancella XS2L.MI per testare Stooq fallback
"""

import duckdb
import os

def test_fallback():
    db_path = os.path.join('data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    # Cancella dati XS2L.MI
    conn.execute('DELETE FROM market_data WHERE symbol = ?', ['XS2L.MI'])
    deleted = conn.execute('SELECT COUNT(*) FROM market_data WHERE symbol = ?', ['XS2L.MI']).fetchone()[0]
    print(f'XS2L.MI records rimanenti: {deleted}')
    
    conn.close()

if __name__ == "__main__":
    test_fallback()
