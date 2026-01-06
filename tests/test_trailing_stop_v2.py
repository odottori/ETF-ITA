#!/usr/bin/env python3
"""
Test Trailing Stop V2 - ETF Italia Project v10.7.4
Test completo trailing stop vero con peak tracking
"""

import sys
import os
import duckdb
import json
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.core.trailing_stop_v2 import (
    create_position_peaks_table,
    initialize_position_peak,
    update_position_peak,
    check_trailing_stop_v2,
    sync_position_peaks_from_ledger
)

def create_test_scenario(conn):
    """Crea scenario di test per trailing stop"""
    
    print("   🎮 Creazione scenario test...")
    
    # 1. Simula posizione aperta su XS2L.MI
    symbol = "XS2L.MI"
    entry_date = datetime.now().date() - timedelta(days=30)
    entry_price = 10.0
    
    # Inserisci posizione nel fiscal_ledger
    conn.execute("""
        INSERT INTO fiscal_ledger (id, date, symbol, type, qty, price)
        VALUES (COALESCE((SELECT MAX(id) FROM fiscal_ledger), 0) + 1, ?, 'XS2L.MI', 'BUY', 100, ?)
    """, [entry_date, entry_price])
    
    # Inizializza peak
    initialize_position_peak(conn, symbol, entry_date, entry_price)
    
    # 2. Simula andamento prezzi
    price_series = [
        (entry_date + timedelta(days=5), 10.5),   # +5%
        (entry_date + timedelta(days=10), 11.5),  # +15% (nuovo peak)
        (entry_date + timedelta(days=15), 11.8),  # +18% (nuovo peak)
        (entry_date + timedelta(days=20), 10.6),  # -10% dal peak (trigger trailing)
        (entry_date + timedelta(days=25), 10.2),  # -13% dal peak
        (datetime.now().date(), 10.0)           # -15% dal peak
    ]
    
    for date, price in price_series:
        # Inserisci prezzo in market_data
        conn.execute("""
            INSERT OR REPLACE INTO market_data (date, symbol, close, high, low, volume)
            VALUES (?, 'XS2L.MI', ?, ?, ?, 1000000)
        """, [date, price, price * 1.02, price * 0.98])
        
        # Aggiorna peak se necessario
        update_position_peak(conn, symbol, price, date)
    
    print(f"   ✅ Scenario test creato per {symbol}")
    return symbol

def test_trailing_stop_logic():
    """Test logica trailing stop v2"""
    
    print("🧪 TRAILING STOP LOGIC TEST - ETF Italia Project v10.7.4")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # Setup
        create_position_peaks_table(conn)
        symbol = create_test_scenario(conn)
        
        # Configurazione trailing stop
        config = {
            'risk_management': {
                'trailing_stop_v2': {
                    'enabled': True,
                    'drawdown_threshold': -0.10,  # -10% dal peak
                    'min_profit_activation': 0.05   # Attiva dopo +5%
                }
            }
        }
        
        # Test vari scenari
        test_scenarios = [
            (10.0, "Entry price"),
            (11.8, "Peak massimo"),
            (10.6, "Trigger trailing (-10% dal peak)"),
            (10.0, "Sotto trailing")
        ]
        
        print("\n2️⃣ Test scenari trailing stop:")
        
        for current_price, scenario_desc in test_scenarios:
            action, reason = check_trailing_stop_v2(conn, config, symbol, current_price)
            
            # Recupera peak per confronto
            peak_data = conn.execute("""
                SELECT peak_price FROM position_peaks 
                WHERE symbol = ? AND is_active = TRUE
            """, [symbol]).fetchone()
            
            if peak_data:
                peak_price = peak_data[0]
                drawdown = (current_price - float(peak_price)) / float(peak_price)
                print(f"   📊 {scenario_desc}: €{current_price:.2f} (DD: {drawdown:+.1%}) → {action or 'NO ACTION'}")
                
                if action:
                    print(f"      🔴 TRIGGER: {reason}")
                else:
                    print(f"      ✅ Nessun trigger")
        
        # 3. Verifica stato finale
        print("\n3️⃣ Verifica stato finale:")
        
        peak_info = conn.execute("""
            SELECT entry_date, peak_price, peak_date 
            FROM position_peaks WHERE symbol = ? AND is_active = TRUE
        """, [symbol]).fetchone()
        
        if peak_info:
            entry_date, peak_price, peak_date = peak_info
            # Recupera entry price dal test scenario
            entry_price = 10.0
            print(f"   📈 Entry: {entry_date} @ €{entry_price:.2f}")
            print(f"   🎯 Peak: {peak_date} @ €{float(peak_price):.2f}")
            
            current_price = conn.execute("""
                SELECT close FROM market_data 
                WHERE symbol = ? ORDER BY date DESC LIMIT 1
            """, [symbol]).fetchone()[0]
            
            final_dd = (current_price - float(peak_price)) / float(peak_price)
            print(f"   📍 Current: €{current_price:.2f} (DD: {final_dd:+.1%})")
        
        conn.commit()
        print("\n   ✅ Test trailing stop completato")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def test_vs_legacy_comparison():
    """Test comparativo trailing stop v2 vs legacy"""
    
    print("\n🔄 COMPARATIVO V2 vs LEGACY")
    print("=" * 40)
    
    print("LEGACY (statico):")
    print("- Stop: -15% vs avg_buy_price")
    print("- Trailing: -10% vs avg_buy_price (non è trailing)")
    print("- Problema: Non segue il massimo favorevole")
    
    print("\nV2 (vero trailing):")
    print("- Stop: -15% vs avg_buy_price")
    print("- Trailing: -10% vs peak_price (vero trailing)")
    print("- Attiva solo dopo +5% profit")
    print("- Peak aggiornato automaticamente")
    
    print("\nEsempio pratico:")
    print("- Entry: €10.00")
    print("- Peak: €12.00 (+20%)")
    print("- Current: €10.80")
    print("  Legacy: No trigger (PnL: +8%)")
    print("  V2: TRIGGER (DD da peak: -10%)")

if __name__ == "__main__":
    success = test_trailing_stop_logic()
    if success:
        test_vs_legacy_comparison()
    sys.exit(0 if success else 1)
