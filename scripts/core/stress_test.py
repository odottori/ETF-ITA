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
    
    print(" STRESS TEST - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        print(" Inizio stress test...")
        
        # 1. Ottieni dati storici per stress test
        print(" Caricamento dati storici...")
        
        # Ottieni dati da market_data per stress test
        portfolio_data = conn.execute("""
        SELECT symbol, date, adj_close, volume
        FROM market_data
        WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        ORDER BY symbol, date
        """).fetchall()
        
        if not portfolio_data:
            print(" Nessun dato storico disponibile per stress test")
            return False
        
        df = pd.DataFrame(portfolio_data, columns=['symbol', 'date', 'adj_close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calcola returns giornalieri per symbol
        df_returns = df.pivot_table(values='adj_close', index='date', columns='symbol')
        df_returns = df_returns.pct_change(fill_method=None).dropna()
        
        # Calcola portfolio returns (equal weight)
        portfolio_returns = df_returns.mean(axis=1).values
        
        print(f"Dati caricati: {len(portfolio_returns)} giorni ({df_returns.index[0].date()} to {df_returns.index[-1].date()})")
        print(f"Simboli: {list(df_returns.columns)}")
        
        # Sanity check dati
        if len(portfolio_returns) < 252:  # Meno di 1 anno di dati
            print("WARNING: Meno di 1 anno di dati storici")
        
        # Check varianza portfolio returns
        portfolio_std = np.std(portfolio_returns)
        if portfolio_std == 0:
            print(" ERROR: Varianza zero nei rendimenti - dati non validi")
            return False
        
        print(f" Portfolio daily return std: {portfolio_std:.4f}")
        
        # 2. Monte Carlo Simulation
        print(f"\n Monte Carlo Simulation (1000 iterazioni)...")
        
        n_simulations = 1000
        results = []
        
        for i in range(n_simulations):
            # Bootstrap sampling con replacement (metodo corretto per Monte Carlo)
            n_days = len(portfolio_returns)
            bootstrap_sample = np.random.choice(portfolio_returns, size=n_days, replace=True)
            
            # Calcola metriche corrette
            cum_returns = np.cumprod(1 + bootstrap_sample)
            
            # CAGR annualizzato corretto
            trading_days = len(cum_returns)
            if trading_days > 0:
                cagr = (cum_returns[-1] ** (252 / trading_days)) - 1
            else:
                cagr = 0
            
            # Max Drawdown calcolo corretto
            peak = np.maximum.accumulate(cum_returns)
            drawdown = (cum_returns / peak) - 1
            max_dd = drawdown.min()
            
            # Sanity check per valori impossibili
            if np.isnan(cagr) or np.isinf(cagr):
                cagr = 0
            if np.isnan(max_dd) or np.isinf(max_dd):
                max_dd = 0
            
            results.append({
                'simulation': i + 1,
                'cagr': cagr,
                'max_dd': max_dd
            })
            
            if (i + 1) % 100 == 0:
                print(f"  Progress: {(i + 1)/n_simulations*100:.1f}%")
        
        # Debug: stampa alcuni CAGR sample per verificare varianza
        if len(results) >= 5:
            sample_cagrs = [r['cagr'] for r in results[:5]]
            print(f" DEBUG: Sample CAGRs: {[f'{c:.4f}' for c in sample_cagrs]}")
        
        # 3. Analisi risultati
        print(f"\n Monte Carlo Results Analysis:")
        
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
        print(f"\n Risk Assessment:")
        
        # Sanity check per risultati impossibili
        if max_dd_mean == 0 and max_dd_std == 0:
            print(" CRITICAL: Max Drawdown identico zero in tutte le simulazioni")
            print("    Questo indica un bug nel calcolo o dati non validi")
            return False
        
        if cagr_std == 0:
            print(" CRITICAL: Varianza CAGR zero - risultati non validi")
            return False
        
        # 5th percentile Max Drawdown check
        if max_dd_5th > -0.25:  # 25% max drawdown
            print(f"️ HIGH RISK: 5th percentile MaxDD > 25% ({max_dd_5th:.1%})")
            print("   ️ Consider reducing position size or increasing diversification")
        else:
            print(" ACCEPTABLE RISK: 5th percentile MaxDD <= 25%")
        
        # Sharpe ratio analysis corretto
        if cagr_std > 0:  # Solo se varianza non zero
            # Sharpe annualizzato corretto (assumendo risk-free rate = 0)
            # CAGR è già annualizzato, std è delle CAGR annualizzate
            sharpe_mean = cagr_mean / cagr_std
            
            # Sanity check Sharpe
            if sharpe_mean > 10:  # Sharpe irrealisticamente alto
                print(f"️ WARNING: Sharpe irrealisticamente alto ({sharpe_mean:.2f})")
                print("   ️ Possibile errore nel calcolo varianza")
            elif sharpe_mean < 0.5:
                print(f" Sharpe Ratio (mean): {sharpe_mean:.2f}")
                print("️ LOW SHARPE: Consider strategy optimization")
            elif sharpe_mean > 1.0:
                print(f" Sharpe Ratio (mean): {sharpe_mean:.2f}")
                print(" EXCELLENT SHARPE: Strategy appears robust")
            else:
                print(f" Sharpe Ratio (mean): {sharpe_mean:.2f}")
        else:
            sharpe_mean = 0
            print(" Sharpe non calcolabile: varianza zero")
        
        # 5. Stress Test Report
        print(f"\n Stress Test Report:")
        
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
        
        # Salva report usando session manager
        try:
            from scripts.core.simple_report_session_manager import SimpleReportSessionManager
            session_manager = SimpleReportSessionManager()
            
            # Crea o aggiungi a session esistente
            latest_session = session_manager.get_latest_session()
            if latest_session:
                timestamp = latest_session.name
            else:
                timestamp, _ = session_manager.create_session()
            
            # Aggiungi stress test alla sessione
            session_manager.add_report_to_session(timestamp, "stress_test", stress_report, "json")
            print(f" Stress test salvato in session: {timestamp}")
            
        except ImportError:
            # Fallback a vecchio metodo
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            stress_file = os.path.join(reports_dir, f"stress_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(stress_file, 'w') as f:
                json.dump(stress_report, f, indent=2)
            print(f" Stress test report salvato: {stress_file}")
        
        # 6. Raccomandazioni
        print(f"\n Raccomandazioni:")
        
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
        
        print(f"\n Stress test completato")
        
        return True
        
    except Exception as e:
        print(f" Errore stress test: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = stress_test()
    sys.exit(0 if success else 1)
