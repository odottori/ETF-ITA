"""Verifica path DB usato da diversi moduli"""
import sys
import os
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager

# Path da path_manager
pm = get_path_manager()
pm_path = str(pm.db_path)

# Path da backtest_engine (hardcoded)
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
be_path = os.path.join(root_dir, 'data', 'etf_data.duckdb')

print("=" * 80)
print("DB PATH VERIFICATION")
print("=" * 80)
print(f"\npath_manager.db_path:")
print(f"  {pm_path}")
print(f"  Exists: {Path(pm_path).exists()}")
print(f"  Size: {Path(pm_path).stat().st_size if Path(pm_path).exists() else 'N/A'}")

print(f"\nbacktest_engine hardcoded path:")
print(f"  {be_path}")
print(f"  Exists: {Path(be_path).exists()}")
print(f"  Size: {Path(be_path).stat().st_size if Path(be_path).exists() else 'N/A'}")

print(f"\nPaths match: {pm_path == be_path}")

# Verifica tabelle in entrambi
import duckdb

if Path(pm_path).exists():
    print(f"\nTables in path_manager DB:")
    conn = duckdb.connect(pm_path, read_only=True)
    tables = conn.execute("SHOW TABLES").fetchdf()
    print(f"  {list(tables['name'])}")
    if 'signals' in list(tables['name']):
        count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        print(f"  signals: {count} rows")
    conn.close()

if Path(be_path).exists() and pm_path != be_path:
    print(f"\nTables in backtest_engine DB:")
    conn = duckdb.connect(be_path, read_only=True)
    tables = conn.execute("SHOW TABLES").fetchdf()
    print(f"  {list(tables['name'])}")
    if 'signals' in list(tables['name']):
        count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        print(f"  signals: {count} rows")
    conn.close()

print("\n" + "=" * 80)
