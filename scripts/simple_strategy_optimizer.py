#!/usr/bin/env python3
"""
Simple Strategy Optimizer - ETF Italia Project v10
Versione semplificata per ottimizzazione strategie
"""

import sys
import os
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def simple_strategy_optimizer():
    """Ottimizzazione strategie semplificata"""
    
    print("🎯 SIMPLE STRATEGY OPTIMIZER - ETF Italia Project v10")
    print("=" * 70)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        print("🔍 Inizio ottimizzazione strategie...")
        
        # 1. Carica dati storici
        print("\n📊 Caricamento dati storici...")
        
        market_data = conn.execute("""
        SELECT symbol, date, adj_close, volume, high, low
        FROM market_data
        WHERE symbol IN ('CSSPX.MI', 'XS2L.MI', '^GSPC')
        ORDER BY symbol, date
        """).fetchall()
        
        if not market_data:
            print("❌ Nessun dato storico disponibile")
            return False
        
        df = pd.DataFrame(market_data, columns=['symbol', 'date', 'adj_close', 'volume', 'high', 'low'])
        df['date'] = pd.to_datetime(df['date'])
        
        # 2. Calcola indicatori tecnici
        print("\n📈 Calcolo indicatori tecnici...")
        
        indicators_data = []
        
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol].copy().sort_values('date')
            
            # SMA
            symbol_data['sma_20'] = symbol_data['adj_close'].rolling(20).mean()
            symbol_data['sma_50'] = symbol_data['adj_close'].rolling(50).mean()
            symbol_data['sma_200'] = symbol_data['adj_close'].rolling(200).mean()
            
            # RSI
            delta = symbol_data['adj_close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            symbol_data['rsi'] = 100 - (100 / (1 + rs))
            
            # Volatilità
            symbol_data['volatility_20d'] = symbol_data['adj_close'].pct_change().rolling(20).std() * np.sqrt(252)
            
            # Momentum
            symbol_data['momentum_12m'] = symbol_data['adj_close'] / symbol_data['adj_close'].shift(252) - 1
            
            indicators_data.append(symbol_data)
        
        indicators_df = pd.concat(indicators_data, ignore_index=True)
        
        # 3. Calcola correlazioni
        print("\n🔗 Analisi correlazioni...")
        
        pivot_data = indicators_df.pivot(index='date', columns='symbol', values='adj_close')
        returns_data = pivot_data.pct_change().dropna()
        correlation_matrix = returns_data.corr()
        
        high_corr_pairs = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                corr = correlation_matrix.iloc[i, j]
                if abs(corr) > 0.7:
                    high_corr_pairs.append((
                        correlation_matrix.columns[i],
                        correlation_matrix.columns[j],
                        corr
                    ))
        
        print(f"📊 Coppie ad alta correlazione (>0.7): {len(high_corr_pairs)}")
        for pair in high_corr_pairs[:5]:
            print(f"  {pair[0]} ↔ {pair[1]}: {pair[2]:.3f}")
        
        # 4. Definizione strategie
        print("\n🎯 Definizione strategie...")
        
        strategies = {
            'trend_following': {
                'name': 'Trend Following SMA 200/50',
                'signals': [],
                'performance': []
            },
            'mean_reversion': {
                'name': 'Mean Reversion RSI',
                'signals': [],
                'performance': []
            },
            'momentum': {
                'name': 'Momentum 12M',
                'signals': [],
                'performance': []
            }
        }
        
        # 5. Backtest strategie
        print("\n🔄 Backtest strategie...")
        
        for symbol in indicators_df['symbol'].unique():
            symbol_data = indicators_df[indicators_df['symbol'] == symbol].copy().sort_values('date')
            
            if len(symbol_data) < 200:
                continue
            
            # Trend Following
            trend_signals = []
            for i in range(200, len(symbol_data)):
                current = symbol_data.iloc[i]
                
                if (current['adj_close'] > current['sma_50'] > current['sma_200']):
                    trend_signals.append(1)  # BUY
                elif (current['adj_close'] < current['sma_50'] < current['sma_200']):
                    trend_signals.append(-1)  # SELL
                else:
                    trend_signals.append(0)  # HOLD
            
            strategies['trend_following']['signals'].extend(trend_signals)
            
            # Mean Reversion
            mr_signals = []
            for i in range(14, len(symbol_data)):
                current = symbol_data.iloc[i]
                
                if current['rsi'] < 30:
                    mr_signals.append(1)  # BUY
                elif current['rsi'] > 70:
                    mr_signals.append(-1)  # SELL
                else:
                    mr_signals.append(0)  # HOLD
            
            strategies['mean_reversion']['signals'].extend(mr_signals)
            
            # Momentum
            mom_signals = []
            for i in range(252, len(symbol_data)):
                current = symbol_data.iloc[i]
                
                if current['momentum_12m'] > 0.05:
                    mom_signals.append(1)  # BUY
                elif current['momentum_12m'] < -0.05:
                    mom_signals.append(-1)  # SELL
                else:
                    mom_signals.append(0)  # HOLD
            
            strategies['momentum']['signals'].extend(mom_signals)
        
        # 6. Calcolo performance
        print("\n📊 Calcolo performance strategie...")
        
        benchmark_returns = returns_data.mean(axis=1)
        
        for strategy_name, strategy_data in strategies.items():
            if not strategy_data['signals']:
                continue
            
            min_len = min(len(benchmark_returns), len(strategy_data['signals']))
            strategy_signals = strategy_data['signals'][:min_len]
            benchmark_ret = benchmark_returns.iloc[:min_len]
            
            strategy_returns = []
            for i, signal in enumerate(strategy_signals):
                if signal == 1:
                    strategy_returns.append(benchmark_ret.iloc[i])
                elif signal == -1:
                    strategy_returns.append(-benchmark_ret.iloc[i])
                else:
                    strategy_returns.append(0)
            
            strategy_returns = pd.Series(strategy_returns)
            
            cagr = (1 + strategy_returns.mean()) ** 252 - 1
            volatility = strategy_returns.std() * np.sqrt(252)
            sharpe = cagr / volatility if volatility > 0 else 0
            
            cumulative = (1 + strategy_returns).cumprod()
            max_dd = (cumulative / cumulative.cummax() - 1).min()
            
            strategy_data['performance'] = {
                'cagr': cagr,
                'volatility': volatility,
                'sharpe': sharpe,
                'max_dd': max_dd,
                'total_return': cumulative.iloc[-1] - 1
            }
            
            print(f"📈 {strategy_data['name']}:")
            print(f"  CAGR: {cagr:.2%} | Sharpe: {sharpe:.2f} | MaxDD: {max_dd:.2%}")
        
        # 7. Ottimizzazione combinazione
        print("\n🎯 Ottimizzazione combinazione strategie...")
        
        best_combination = None
        best_sharpe = -float('inf')
        
        strategy_names = list(strategies.keys())
        
        for i in range(len(strategy_names)):
            for j in range(i+1, len(strategy_names)):
                combo = [strategy_names[i], strategy_names[j]]
                
                combo_performance = calculate_combination_performance(
                    strategies, combo, benchmark_returns
                )
                
                if combo_performance['sharpe'] > best_sharpe:
                    best_sharpe = combo_performance['sharpe']
                    best_combination = {
                        'strategies': combo,
                        'performance': combo_performance
                    }
        
        # 8. Risultati finali
        print(f"\n🎯 RIEPILOGO OTTIMIZZAZIONE:")
        
        if best_combination:
            combo = best_combination
            print(f"🏆 Migliore combinazione ({combo['performance']['sharpe']:.2f} Sharpe):")
            for strategy in combo['strategies']:
                print(f"  • {strategies[strategy]['name']}")
            
            print(f"\n📊 Performance vs Benchmark:")
            print(f"  Strategy CAGR: {combo['performance']['cagr']:.2%}")
            print(f"  Benchmark CAGR: {benchmark_returns.mean() * 252:.2%}")
            print(f"  Alpha: {combo['performance']['cagr'] - benchmark_returns.mean() * 252:+.2%}")
            print(f"  Strategy Sharpe: {combo['performance']['sharpe']:.2f}")
            print(f"  Benchmark Sharpe: {benchmark_returns.mean() / (benchmark_returns.std() * np.sqrt(252)):.2f}")
        
        # 9. Salva risultati
        print(f"\n💾 Salvando risultati...")
        
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        optimal_config = {
            'timestamp': datetime.now().isoformat(),
            'best_combination': best_combination,
            'correlation_analysis': {
                'high_correlation_pairs': high_corr_pairs,
                'correlation_matrix': correlation_matrix.to_dict()
            },
            'strategy_weights': {
                strategy: 0.5 for strategy in best_combination['strategies']
            } if best_combination else {}
        }
        
        config_file = os.path.join(reports_dir, f"simple_optimal_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(config_file, 'w') as f:
            json.dump(optimal_config, f, indent=2, default=str)
        
        print(f"📄 Configurazione ottimale salvata: {config_file}")
        
        print(f"\n✅ Ottimizzazione completata")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore ottimizzazione: {e}")
        return False
        
    finally:
        conn.close()

def calculate_combination_performance(strategies, combo, benchmark_returns):
    """Calcola performance combinazione strategie"""
    
    weights = [1/len(combo)] * len(combo)
    
    min_len = len(benchmark_returns)
    combined_signals = []
    
    for i in range(min_len):
        signal_sum = 0
        for j, strategy_name in enumerate(combo):
            if i < len(strategies[strategy_name]['signals']):
                signal_sum += strategies[strategy_name]['signals'][i] * weights[j]
        
        if signal_sum > 0.5:
            combined_signals.append(1)
        elif signal_sum < -0.5:
            combined_signals.append(-1)
        else:
            combined_signals.append(0)
    
    strategy_returns = []
    for i, signal in enumerate(combined_signals):
        if signal == 1:
            strategy_returns.append(benchmark_returns.iloc[i])
        elif signal == -1:
            strategy_returns.append(-benchmark_returns.iloc[i])
        else:
            strategy_returns.append(0)
    
    strategy_returns = pd.Series(strategy_returns)
    
    cagr = (1 + strategy_returns.mean()) ** 252 - 1
    volatility = strategy_returns.std() * np.sqrt(252)
    sharpe = cagr / volatility if volatility > 0 else 0
    
    cumulative = (1 + strategy_returns).cumprod()
    max_dd = (cumulative / cumulative.cummax() - 1).min()
    
    return {
        'cagr': cagr,
        'volatility': volatility,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'total_return': cumulative.iloc[-1] - 1
    }

if __name__ == "__main__":
    success = simple_strategy_optimizer()
    sys.exit(0 if success else 1)
