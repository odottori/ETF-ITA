#!/usr/bin/env python3
"""
Setup Symbol Registry - ETF Italia Project v10
Crea tabella symbol_registry per gestione simboli attivi
"""

import sys
import os
import json
import duckdb
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_symbol_registry():
    """Crea tabella symbol_registry con simboli attivi"""
    
    print("🔧 SETUP SYMBOL REGISTRY - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        print("📊 Creazione tabella symbol_registry...")
        
        # Crea tabella symbol_registry
        conn.execute("""
        CREATE TABLE IF NOT EXISTS symbol_registry (
            symbol VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            status VARCHAR DEFAULT 'ACTIVE',
            category VARCHAR DEFAULT 'ETF',
            currency VARCHAR DEFAULT 'EUR',
            distribution_policy VARCHAR DEFAULT 'ACC',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Crea indici
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_registry_status ON symbol_registry(status)")
        conn.execute(" CREATE INDEX IF NOT EXISTS idx_symbol_registry_category ON symbol_registry(category)")
        
        # Pulisci dati esistenti
        conn.execute("DELETE FROM symbol_registry")
        
        # Inserisci simboli dal config
        symbols_to_insert = []
        
        # Core ETFs
        for etf in config['universe']['core']:
            symbols_to_insert.append((
                etf['symbol'],
                etf.get('name', etf['symbol']),
                True,
                'ACTIVE',
                'ETF',
                etf.get('currency', 'EUR'),
                etf.get('distribution_policy', 'ACC'),
                datetime.now(),
                datetime.now()
            ))
        
        # Satellite ETFs
        for etf in config['universe']['satellite']:
            symbols_to_insert.append((
                etf['symbol'],
                etf.get('name', etf['symbol']),
                True,
                'ACTIVE',
                'ETF',
                etf.get('currency', 'EUR'),
                etf.get('distribution_policy', 'ACC'),
                datetime.now(),
                datetime.now()
            ))
        
        # Benchmark
        if 'benchmark' in config:
            for etf in config['universe']['benchmark']:
                symbols_to_insert.append((
                    etf['symbol'],
                    etf.get('name', etf['symbol']),
                    True,
                    'ACTIVE',
                    etf.get('category', 'INDEX'),
                    etf.get('currency', 'USD'),
                    etf.get('distribution_policy', 'NONE'),
                    datetime.now(),
                    datetime.now()
                ))
        
        # Inserisci i dati
        conn.executemany("""
        INSERT INTO symbol_registry (symbol, name, is_active, status, category, currency, distribution_policy, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, symbols_to_insert)
        
        print(f"✅ Inseriti {len(symbols_to_insert)} simboli")
        
        # Report
        print(f"\n📊 SYMBOL REGISTRY REPORT:")
        print("-" * 40)
        
        all_symbols = conn.execute("SELECT * FROM symbol_registry ORDER BY category, symbol").fetchall()
        
        for symbol in all_symbols:
            sym, name, active, status, category, currency, dist_policy, created, updated = symbol
            status_emoji = "✅" if active else "❌"
            print(f"{status_emoji} {sym} ({name}) - {category} - {currency} - {dist_policy}")
        
        conn.commit()
        
        print(f"\n🎉 SYMBOL REGISTRY SETUP COMPLETED")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore setup symbol registry: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = setup_symbol_registry()
    sys.exit(0 if success else 1)
