#!/usr/bin/env python3
"""
Stress Test - ETF Italia Project v10
Monte Carlo smoke test e stress analysis
"""

import sys
import os
import json
import duckdb
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def stress_test():
    """Esegue stress test con Monte Carlo"""
    
    print("🔥 STRESS TEST - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        print("🔍 Inizio stress test...")
        
        # 1. Ottieni dati storici per stress test
        print("📊 Caricamento dati storici...")
        
        # Ottieni returns giornalieri per portfolio
        portfolio_returns = conn.execute("""
        SELECT date, adj_close, volume
        FROM portfolio_overview
        ORDER BY date
        """).fetchall()
        
        if not portfolio_returns:
            print("❌ Nessun dato storico disponibile per stress test")
            return False
        
        df = pd.DataFrame(portfolio_returns, columns=['date', 'adj_close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calcola returns giornalieri
        df['daily_return'] = df['adj_close'].pct_change()
        df = df.dropna()
        
        returns = df['daily_return'].values
        
        print(f"📊 Dati caricati: {len(returns)} giorni ({df.index[0].date} → {df.index[-1].date})")
        
        # 2. Monte Carlo Simulation
        print(f"\n🎲 Monte Carlo Simulation (1000 iterazioni)...")
        
        n_simulations = 1000
        results = []
        
        for i in range(n_simulations):
            # Shuffle returns
            shuffled_returns = np.random.permutation(returns)
            
            # Calcola metriche
            cum_returns = np.cumprod(1 + shuffled_returns)
            cagr = (cum_returns[-1] ** (252 / len(cum_returns))) - 1
            max_dd = (np.maximum.accumulate(cum_returns / np.maximum.accumulate(cum_returns)) - 1).min()
            
            results.append({
                'simulation': i + 1,
                'cagr': cagr,
                'max_dd': max_dd
            })
            
            print(f"  Progress: {(i + 1)/n_simulations*100:.1f}%")
        
        # 3. Analisi risultati
        print(f"\n📊 Monte Carlo Results Analysis:")
        
        cagr_values = [r['cagr'] for r in results]
        max_dd_values = [r['max_dd'] for r in results]
        
        # Statistiche
        cagr_mean = np.mean(cagr_values)
        cagr_std = np.std(cagr_values)
        cagr_5th = np.percentile(cagr_values, 5)
        cagr_95th = np.percentile(cagr_values, 95)
        
        max_dd_mean = np.mean(max_dd_values)
        max_dd_std = np.std(max_dd_values)
        max_dd_5th = np.percentile(max_dd_values, 5)
        max_dd_95th = np.percentile(max_dd_values, 95)
        
        print(f"CAGR:")
        print(f"  Mean: {cagr_mean:.2%}")
        print(f"  Std Dev: {cagr_std:.2%}")
        print(f"   5th percentile: {cagr_5th:.2%}")
        print(f"  95th percentile: {cagr_95th:.2%}")
        
        print(f"\nMax Drawdown:")
        print(f"  Mean: {max_dd_mean:.2%}")
        print(f"  Std Dev: {max_dd_std:.2%}")
        print(f"   5th percentile: {max_dd_5th:.2%}")
        print(f"  95th percentile: {max_dd_95th:.2%}")
        
        # 4. Risk Assessment
        print(f"\n🎯 Risk Assessment:")
        
        # 5th percentile Max Drawdown check
        if max_dd_5th > -0.25:  # 25% max drawdown
            print(f"⚠️ HIGH RISK: 5th percentile MaxDD > 25% ({max_dd_5th:.1%})")
            print("   ⚠️ Consider reducing position size or increasing diversification")
        else:
            print("✅ ACCEPTABLE RISK: 5th percentile MaxDD ≤ 25%")
        
        # Sharpe ratio analysis
        if cagr_mean > 0 and cagr_std > 0:
            sharpe_mean = cagr_mean / cagr_std
            print(f"📈 Sharpe Ratio (mean): {sharpe_mean:.2f}")
            
            if sharpe_mean < 0.5:
                print("⚠️ LOW SHARPE: Consider strategy optimization")
            elif sharpe_mean > 1.0:
                print("✅ EXCELLENT SHARPE: Strategy appears robust")
        
        # 5. Stress Test Report
        print(f"\n📋 Stress Test Report:")
        
        stress_report = {
            'timestamp': datetime.now().isoformat(),
            'n_simulations': n_simulations,
            'cagr_stats': {
                'mean': cagr_mean,
                'std': cagr_std,
                'min': min(cagr_values),
                'max': max(cagr_values),
                'p5': cagr_5th,
                'p95': cagr_95th
            },
            'max_dd_stats': {
                'mean': max_dd_mean,
                'std': max_dd_std,
                'min': min(max_dd_values),
                'max': max(max_dd_values),
                'p5': max_dd_5th,
                'p95': max_dd_95th
            },
            'risk_assessment': {
                'max_dd_5th_pct': max_dd_5th,
                'sharpe_mean': sharpe_mean if cagr_mean > 0 else 0,
                'risk_level': 'HIGH' if max_dd_5th > -0.25 else 'ACCEPTABLE'
            }
        }
        
        # Salva report
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        stress_file = os.path.join(reports_dir, f"stress_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(stress_file, 'w') as f:
            json.dump(stress_report, f, indent=2)
        
        print(f"📄 Stress test report salvato: {stress_file}")
        
        # 6. Raccomandazioni
        print(f"\n💡 Raccomandazioni:")
        
        if max_dd_5th > -0.25:
            print("  • Ridurre sizing per posizione")
            print("  • Considerare stop-loss automatici")
            print("  • Aumenta diversificazione")
        
        if cagr_mean < 0.05:
            print("  • Rivedi strategia segnali")
            print("  * Considera mean reversion o momentum")
            print("  * Verifica cost model realistico")
        
        if sharpe_mean < 0.5:
            print("  * Ottimizza risk-adjusted returns")
            print("  * Considera Kelly Criterion sizing")
            print("  • Riduci turnover")
        
        print(f"\n✅ Stress test completato")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore stress test: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = stress_test()
    sys.exit(0 if success else 1)
