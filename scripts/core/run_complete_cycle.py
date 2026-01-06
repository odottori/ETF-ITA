#!/usr/bin/env python3
"""
Run Complete Cycle - ETF Italia Project v10
Esegue la catena completa: signals → strategy → execute → ledger
"""

import sys
import os
import subprocess
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_complete_cycle(commit=False):
    """Esegue l'intero ciclo di trading"""
    
    print(" COMPLETE TRADING CYCLE - ETF Italia Project v10")
    print("=" * 60)
    
    if commit:
        print("⚠️  COMMIT MODE - Le modifiche saranno salvate nel database")
    else:
        print("📋 DRY-RUN MODE - Nessuna modifica permanente")
    
    scripts_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(os.path.dirname(scripts_dir))
    
    try:
        # 1. Compute Signals
        print("\n🔍 STEP 1: Compute Signals")
        print("-" * 40)
        
        signals_script = os.path.join(scripts_dir, 'core', 'compute_signals.py')
        result = subprocess.run([sys.executable, signals_script], 
                              capture_output=True, text=True, cwd=root_dir)
        
        if result.returncode != 0:
            print(f"❌ Compute Signals fallito:")
            print(result.stderr)
            return False
        
        print("✅ Compute Signals completato")
        
        # 2. Strategy Engine
        print("\n🎯 STEP 2: Strategy Engine")
        print("-" * 40)
        
        strategy_script = os.path.join(scripts_dir, 'core', 'strategy_engine.py')
        strategy_args = [sys.executable, strategy_script]
        
        if not commit:
            strategy_args.append('--dry-run')
        else:
            strategy_args.append('--commit')
        
        result = subprocess.run(strategy_args, 
                              capture_output=True, text=True, cwd=root_dir)
        
        if result.returncode != 0:
            print(f"❌ Strategy Engine fallito:")
            print(result.stderr)
            return False
        
        print("✅ Strategy Engine completato")
        
        # 3. Update Ledger (se commit)
        if commit:
            print("\n📊 STEP 3: Update Ledger")
            print("-" * 40)
            
            ledger_script = os.path.join(scripts_dir, 'core', 'update_ledger.py')
            result = subprocess.run([sys.executable, ledger_script, '--commit'], 
                                  capture_output=True, text=True, cwd=root_dir)
            
            if result.returncode != 0:
                print(f"❌ Update Ledger fallito:")
                print(result.stderr)
                return False
            
            print("✅ Update Ledger completato")
        
        # 4. Report finale
        print(f"\n🎉 CICLO COMPLETATO CON SUCCESSO")
        print(f"{'-' * 40}")
        print(f"Mode: {'COMMIT' if commit else 'DRY-RUN'}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if commit:
            print(f"✅ Tutte le modifiche sono state salvate nel database")
        else:
            print(f"📋 Dry-run completato - nessuna modifica permanente")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore durante il ciclo: {e}")
        return False

def show_status():
    """Mostra stato attuale del sistema"""
    
    print("📊 SISTEM STATUS - ETF Italia Project v10")
    print("=" * 60)
    
    scripts_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(os.path.dirname(scripts_dir))
    
    try:
        # 1. Ultimi segnali
        print("\n🔍 Ultimi segnali:")
        print("-" * 30)
        
        import duckdb
        import json
        
        config_path = os.path.join(root_dir, 'config', 'etf_universe.json')
        db_path = os.path.join(root_dir, 'data', 'etf_data.duckdb')
        
        if not os.path.exists(db_path):
            print("❌ Database non trovato")
            return
        
        conn = duckdb.connect(db_path)
        
        signals = conn.execute("""
        SELECT symbol, signal_state, risk_scalar, explain_code
        FROM signals 
        WHERE date = (SELECT MAX(date) FROM signals)
        ORDER BY symbol
        """).fetchall()
        
        for symbol, state, scalar, explain in signals:
            emoji = "" if state == "RISK_ON" else "" if state == "RISK_OFF" else ""
            print(f"{emoji} {symbol}: {state} (scalar: {scalar:.3f})")
        
        # 2. Posizioni correnti
        print(f"\n💼 Posizioni correnti:")
        print("-" * 30)
        
        positions = conn.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
            AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_price
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        ORDER BY symbol
        """).fetchall()
        
        if positions:
            for symbol, qty, avg_price in positions:
                print(f"  {symbol}: {qty:,.0f} @ €{avg_price:.2f}")
        else:
            print("  Nessuna posizione aperta")
        
        # 3. Ultimi ordini
        print(f"\n📋 Ultimi ordini:")
        print("-" * 30)
        
        orders_dir = os.path.join(root_dir, 'data', 'orders')
        if os.path.exists(orders_dir):
            order_files = [f for f in os.listdir(orders_dir) if f.startswith('orders_') and f.endswith('.json')]
            if order_files:
                order_files.sort(reverse=True)
                latest_orders = os.path.join(orders_dir, order_files[0])
                
                with open(latest_orders, 'r') as f:
                    orders_data = json.load(f)
                
                orders = orders_data.get('orders', [])
                timestamp = orders_data.get('timestamp', 'Unknown')
                
                print(f"  Timestamp: {timestamp}")
                print(f"  Total: {len(orders)} ordini")
                
                buy_count = len([o for o in orders if o['action'] == 'BUY'])
                sell_count = len([o for o in orders if o['action'] == 'SELL'])
                hold_count = len([o for o in orders if o['action'] == 'HOLD'])
                
                print(f"  BUY: {buy_count} | SELL: {sell_count} | HOLD: {hold_count}")
            else:
                print("  Nessun file ordini trovato")
        else:
            print("  Directory ordini non trovata")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Errore status: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Complete Trading Cycle ETF Italia Project')
    parser.add_argument('--commit', action='store_true', help='Commit changes to database')
    parser.add_argument('--status', action='store_true', help='Show system status only')
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
    else:
        success = run_complete_cycle(commit=args.commit)
        sys.exit(0 if success else 1)
