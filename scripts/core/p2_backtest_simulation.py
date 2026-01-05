#!/usr/bin/env python3
"""
P2 Backtest Simulation - ETF Italia Project v10
Simulazione storica effetti correzioni P2
"""

import sys
import os
import json
import duckdb
import numpy as np
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_backtest_simulation():
    """Simula performance storica delle strategie corrette"""
    
    print("📈 P2 — Backtest Simulation: Impatto Storico Correzioni")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # Recupera dati storici
        print("\n📊 Caricamento dati storici...")
        
        historical_data = conn.execute("""
        WITH daily_returns AS (
            SELECT 
                symbol,
                date,
                close,
                (close / LAG(close) OVER (PARTITION BY symbol ORDER BY date) - 1) as daily_return
            FROM market_data 
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND close IS NOT NULL
            AND date >= '2020-01-01'
        ),
        pivot_data AS (
            SELECT 
                date,
                MAX(CASE WHEN symbol = 'CSSPX.MI' THEN close END) as csspx_close,
                MAX(CASE WHEN symbol = 'XS2L.MI' THEN close END) as xs2l_close,
                MAX(CASE WHEN symbol = 'CSSPX.MI' THEN daily_return END) as csspx_return,
                MAX(CASE WHEN symbol = 'XS2L.MI' THEN daily_return END) as xs2l_return
            FROM daily_returns
            GROUP BY date
            HAVING csspx_close IS NOT NULL AND xs2l_close IS NOT NULL
        )
        SELECT 
            date,
            csspx_close,
            xs2l_close,
            csspx_return,
            xs2l_return
        FROM pivot_data
        ORDER BY date
        """).fetchall()
        
        if not historical_data:
            print("❌ Dati storici insufficienti")
            return False
        
        print(f"   📅 Periodo: {historical_data[0][0]} → {historical_data[-1][0]}")
        print(f"   📊 Observations: {len(historical_data)} giorni")
        
        # Simula bond ETF (sintetico)
        np.random.seed(42)  # Per riproducibilità
        bond_returns = np.random.normal(0.0003, 0.005, len(historical_data))  # 8% vol, 7.5% annuo
        
        # Scenari di portafoglio
        scenarios = {
            'original': {
                'name': 'Originale (50/50)',
                'weights': {'CSSPX.MI': 0.5, 'XS2L.MI': 0.5, 'BOND.MI': 0.0},
                'description': 'Portfolio attuale senza correzioni'
            },
            'rebalanced': {
                'name': 'Ribilanciato (60/40)',
                'weights': {'CSSPX.MI': 0.6, 'XS2L.MI': 0.4, 'BOND.MI': 0.0},
                'description': 'Ribilanciamento pesi per ridurre concentrazione'
            },
            'diversified': {
                'name': 'Diversificato (+Bond)',
                'weights': {'CSSPX.MI': 0.5, 'XS2L.MI': 0.3, 'BOND.MI': 0.2},
                'description': 'Aggiunta bond per diversificazione'
            },
            'vol_targeted': {
                'name': 'Vol Targeted',
                'weights': {'CSSPX.MI': 0.49, 'XS2L.MI': 0.49, 'BOND.MI': 0.02},
                'description': 'Vol targeting con cash buffer'
            }
        }
        
        # Calcola performance per ogni scenario
        results = {}
        
        for scenario_id, scenario in scenarios.items():
            print(f"\n📊 Simulazione: {scenario['name']}")
            print("-" * 40)
            
            weights = scenario['weights']
            
            # Inizializza serie storiche
            portfolio_values = [10000]  # Starting value
            portfolio_returns = []
            
            for i, row in enumerate(historical_data):
                date, csspx_close, xs2l_close, csspx_return, xs2l_return = row
                
                # Salta giorni con dati mancanti
                if csspx_return is None or xs2l_return is None:
                    portfolio_returns.append(0.0)  # Return nullo per giorni mancanti
                    new_value = portfolio_values[-1]
                    portfolio_values.append(new_value)
                    continue
                
                # Calcola return giornaliero portfolio
                daily_return = (
                    weights['CSSPX.MI'] * csspx_return +
                    weights['XS2L.MI'] * xs2l_return +
                    weights['BOND.MI'] * bond_returns[i]
                )
                
                portfolio_returns.append(daily_return)
                new_value = portfolio_values[-1] * (1 + daily_return)
                portfolio_values.append(new_value)
            
            # Calcola metriche performance
            portfolio_returns_array = np.array(portfolio_returns)
            
            # Total return
            total_return = (portfolio_values[-1] / portfolio_values[0]) - 1
            
            # Annualized metrics
            trading_days = len(portfolio_returns)
            years = trading_days / 252
            
            annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
            annual_vol = np.std(portfolio_returns_array) * np.sqrt(252)
            sharpe_ratio = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0
            
            # Drawdown analysis
            peak = np.maximum.accumulate(portfolio_values)
            drawdown = (portfolio_values - peak) / peak
            max_drawdown = np.min(drawdown)
            
            # Calcola giorni di drawdown
            dd_days = np.sum(drawdown < -0.1)  # Giorni con DD > -10%
            
            # Risk metrics
            var_95 = np.percentile(portfolio_returns_array, 5)  # 5th percentile
            skewness = calculate_skewness(portfolio_returns_array)
            
            results[scenario_id] = {
                'scenario': scenario['name'],
                'description': scenario['description'],
                'weights': weights,
                'performance': {
                    'total_return': total_return,
                    'annual_return': annual_return,
                    'annual_volatility': annual_vol,
                    'sharpe_ratio': sharpe_ratio,
                    'max_drawdown': max_drawdown,
                    'dd_days_10pct': dd_days,
                    'var_95_daily': var_95,
                    'skewness': skewness,
                    'final_value': portfolio_values[-1],
                    'trading_days': trading_days
                }
            }
            
            print(f"   📈 Return Totale: {total_return:+.1%}")
            print(f"   📊 Return Ann.: {annual_return:+.1%}")
            print(f"   🎯 Volatilità: {annual_vol:.1%}")
            print(f"   📈 Sharpe: {sharpe_ratio:.2f}")
            print(f"   📉 Max DD: {max_drawdown:.1%}")
            print(f"   📅 Giorni DD > -10%: {dd_days}")
        
        # Tabella comparativa finale
        print(f"\n📋 TABELLA COMPARATIVA PERFORMANCE")
        print("=" * 80)
        print(f"{'Scenario':<20} {'Ret Ann':<8} {'Vol':<8} {'Sharpe':<8} {'Max DD':<8} {'DD Giorni':<10}")
        print("-" * 80)
        
        for scenario_id, result in results.items():
            perf = result['performance']
            print(f"{result['scenario']:<20} {perf['annual_return']:<+8.1%} {perf['annual_volatility']:<8.1%} {perf['sharpe_ratio']:<8.2f} {perf['max_drawdown']:<8.1%} {perf['dd_days_10pct']:<10}")
        
        # Analisi miglioramenti
        print(f"\n💡 ANALISI MIGLIORAMENTI")
        print("-" * 30)
        
        original = results['original']['performance']
        
        for scenario_id, result in results.items():
            if scenario_id == 'original':
                continue
                
            current = result['performance']
            
            return_improvement = current['annual_return'] - original['annual_return']
            vol_reduction = current['annual_volatility'] - original['annual_volatility']
            sharpe_improvement = current['sharpe_ratio'] - original['sharpe_ratio']
            dd_improvement = current['max_drawdown'] - original['max_drawdown']
            
            print(f"\n📊 {result['scenario']}:")
            print(f"   Return: {return_improvement:+.1%} ({return_improvement/original['annual_return']*100:+.1f}%)")
            print(f"   Volatilità: {vol_reduction:+.1%} ({vol_reduction/original['annual_volatility']*100:+.1f}%)")
            print(f"   Sharpe: {sharpe_improvement:+.2f}")
            print(f"   Max DD: {dd_improvement:+.1%}")
        
        # Raccomandazione basata su risk-adjusted performance
        print(f"\n🎯 RACCOMANDAZIONE BASED ON BACKTEST")
        print("-" * 40)
        
        # Trova best Sharpe ratio
        best_sharpe_scenario = max(results.keys(), key=lambda x: results[x]['performance']['sharpe_ratio'])
        best_sharpe = results[best_sharpe_scenario]
        
        # Trova min drawdown
        best_dd_scenario = min(results.keys(), key=lambda x: results[x]['performance']['max_drawdown'])
        best_dd = results[best_dd_scenario]
        
        # Trova best risk-adjusted (Sharpe + DD)
        risk_adjusted_scores = {}
        for scenario_id, result in results.items():
            perf = result['performance']
            # Score = Sharpe - (max_drawdown * 2)  # Penalità drawdown
            risk_adjusted_scores[scenario_id] = perf['sharpe_ratio'] - (perf['max_drawdown'] * 2)
        
        best_risk_adj_scenario = max(risk_adjusted_scores.keys(), key=risk_adjusted_scores.get)
        best_risk_adj = results[best_risk_adj_scenario]
        
        print(f"🏆 Miglior Sharpe: {best_sharpe['scenario']} ({best_sharpe['performance']['sharpe_ratio']:.2f})")
        print(f"🛡️ Min Drawdown: {best_dd['scenario']} ({best_dd['performance']['max_drawdown']:.1%})")
        print(f"⚖️ Risk-Adjusted: {best_risk_adj['scenario']} (score: {risk_adjusted_scores[best_risk_adj_scenario]:.2f})")
        
        # Salva risultati
        backtest_results = {
            'timestamp': datetime.now().isoformat(),
            'backtest_simulation': {
                'period': {
                    'start': historical_data[0][0],
                    'end': historical_data[-1][0],
                    'trading_days': len(historical_data)
                },
                'scenarios': results,
                'analysis': {
                    'best_sharpe': {
                        'scenario': best_sharpe_scenario,
                        'sharpe_ratio': best_sharpe['performance']['sharpe_ratio']
                    },
                    'best_drawdown': {
                        'scenario': best_dd_scenario,
                        'max_drawdown': best_dd['performance']['max_drawdown']
                    },
                    'best_risk_adjusted': {
                        'scenario': best_risk_adj_scenario,
                        'score': risk_adjusted_scores[best_risk_adj_scenario]
                    }
                }
            }
        }
        
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            report_file = sm.add_report_to_session('analysis', backtest_results, 'json')
            print(f"\n📋 Backtest completo salvato: {report_file}")
        except ImportError:
            print(f"\n⚠️ Session Manager non disponibile")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def calculate_skewness(returns):
    """Calcola skewness dei returns"""
    if len(returns) < 2:
        return 0
    
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    
    if std_return == 0:
        return 0
    
    skewness = np.mean(((returns - mean_return) / std_return) ** 3)
    return skewness

if __name__ == "__main__":
    success = run_backtest_simulation()
    sys.exit(0 if success else 1)
