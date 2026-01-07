"""
Inspect DB schema to understand available tables and data.
"""
import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "etf_data.duckdb"

def main():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    
    print("=" * 80)
    print("DB SCHEMA INSPECTION")
    print("=" * 80)
    
    # List all tables
    print("\n### TABLES ###")
    tables = conn.execute("SHOW TABLES").fetchdf()
    print(tables.to_string(index=False))
    
    # For each table, show schema and row count
    for table_name in tables['name']:
        print(f"\n### TABLE: {table_name} ###")
        
        # Schema
        schema = conn.execute(f"DESCRIBE {table_name}").fetchdf()
        print("\nSchema:")
        print(schema.to_string(index=False))
        
        # Row count
        count = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}").fetchdf()
        print(f"\nRow count: {count['count'].iloc[0]}")
        
        # Sample data (first 3 rows)
        if count['count'].iloc[0] > 0:
            sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchdf()
            print("\nSample data:")
            print(sample.to_string(index=False))
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
