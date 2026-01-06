#!/usr/bin/env python3
"""
Stress Test Monte Carlo - ETF Italia Project v003
Simulazione stress testing per valutare robustezza portafoglio
"""

import sys
import os
import json
import duckdb
from datetime import datetime, timedelta
import numpy as np

# Aggiungi path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def stress_test_monte_carlo(db_path, num_simulations=1000, time_horizon_days=252):
    """
    Esegue Monte Carlo stress test sul portafoglio attuale
    """
    
    print("🎲 MONTE CARLO STRESS TEST")
    print("=" * 50)
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Ottenere posizioni attuali
        positions = conn.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
            AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_price
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        """).fetchall()
        
        if not positions:
            print("❌ Nessuna posizione trovata")
            return False
        
        # 2. Ottenere dati storici per volatilità
        volatility_data = {}
        for symbol, _, _ in positions:
            vol_data = conn.execute("""
            SELECT 
                (adj_close / LAG(adj_close) OVER (ORDER BY date) - 1) as daily_return
            FROM market_data 
            WHERE symbol = ? AND adj_close IS NOT NULL
            ORDER BY date DESC 
            LIMIT 252
            """, [symbol]).fetchall()
            
            if vol_data:
                returns = [r[0] for r in vol_data if r[0] is not None]
                if returns:
                    volatility_data[symbol] = np.std(returns) * np.sqrt(252)
        
        # 3. Simulazioni Monte Carlo
        portfolio_values = []
        worst_scenarios = []
        
        for sim in range(num_simulations):
            portfolio_value = 0
            
            for symbol, qty, avg_price in positions:
                if symbol in volatility_data:
                    vol = volatility_data[symbol]
                    
                    # Simulazione geometric Brownian motion
                    daily_returns = np.random.normal(0, vol/np.sqrt(252), time_horizon_days)
                    final_return = np.prod(1 + daily_returns) - 1
                    
                    # Prezzo finale simulato
                    current_price = conn.execute("""
                    SELECT adj_close FROM market_data 
                    WHERE symbol = ? 
                    ORDER BY date DESC LIMIT 1
                    """, [symbol]).fetchone()[0]
                    
                    final_price = current_price * (1 + final_return)
                    position_value = qty * final_price
                    portfolio_value += position_value
            
            portfolio_values.append(portfolio_value)
            
            # Track worst 5% scenarios
            if sim < int(num_simulations * 0.05):
                worst_scenarios.append(portfolio_value)
        
        # 4. Calcoli statistici
        portfolio_values = np.array(portfolio_values)
        current_portfolio_value = sum(qty * conn.execute("""
        SELECT adj_close FROM market_data 
        WHERE symbol = ? ORDER BY date DESC LIMIT 1
        """, [symbol]).fetchone()[0] for symbol, qty, _ in positions)
        
        stats = {
            'current_portfolio_value': current_portfolio_value,
            'mean_final_value': np.mean(portfolio_values),
            'std_final_value': np.std(portfolio_values),
            'percentile_5': np.percentile(portfolio_values, 5),
            'percentile_95': np.percentile(portfolio_values, 95),
            'worst_case': np.min(portfolio_values),
            'best_case': np.max(portfolio_values),
            'var_95': current_portfolio_value - np.percentile(portfolio_values, 5),
            'cvar_95': current_portfolio_value - np.mean(worst_scenarios),
            'max_drawdown_estimate': (current_portfolio_value - np.min(portfolio_values)) / current_portfolio_value,
            'volatility_estimate': np.std(portfolio_values) / np.mean(portfolio_values),
            'num_simulations': num_simulations,
            'time_horizon_days': time_horizon_days,
            'positions_analyzed': len(positions)
        }
        
        # 5. Output
        print(f"💰 Current Portfolio Value: €{current_portfolio_value:,.2f}")
        print(f"📊 Expected Final Value: €{stats['mean_final_value']:,.2f}")
        print(f"⚠️  5th Percentile: €{stats['percentile_5']:,.2f}")
        print(f"📈 95th Percentile: €{stats['percentile_95']:,.2f}")
        print(f"🔻 Worst Case: €{stats['worst_case']:,.2f}")
        print(f"📉 VaR 95%: €{stats['var_95']:,.2f}")
        print(f"⚡ CVaR 95%: €{stats['cvar_95']:,.2f}")
        print(f"📉 Max DD Estimate: {stats['max_drawdown_estimate']:.1%}")
        
        # 6. Salva risultati
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"data/reports/sessions/{timestamp}/05_stress_tests"
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = f"{output_dir}/stress_test_{timestamp}.json"
        with open(output_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"📁 Results saved to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during stress test: {e}")
        return False
    finally:
        conn.close()

def main():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    success = stress_test_monte_carlo(db_path)
    
    if success:
        print("\n✅ Stress test completed successfully")
        return 0
    else:
        print("\n❌ Stress test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
