#!/usr/bin/env python3
"""
Auto Strategy Optimizer - ETF Italia Project v10
Sistema autonomo per ottimizzazione strategie e sovraperformance indice
"""

import sys
import os
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def auto_strategy_optimizer():
    """Ottimizzazione automatica strategie per sovraperformance"""
    
    print("🤖 AUTO STRATEGY OPTIMIZER - ETF Italia Project v10")
    print("=" * 70)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        print("🔍 Inizio ottimizzazione automatica strategie...")
        
        # 1. Carica dati storici completi
        print("\n📊 Caricamento dati storici per analisi...")
        
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
        
        # 2. Calcola indicatori tecnici per ogni simbolo
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
            
            # Stagionalità (mese)
            symbol_data['month'] = symbol_data['date'].dt.month
            symbol_data['day_of_week'] = symbol_data['date'].dt.dayofweek
            
            indicators_data.append(symbol_data)
        
        indicators_df = pd.concat(indicators_data, ignore_index=True)
        
        # 3. Analisi correlazioni
        print("\n🔗 Analisi correlazioni tra strumenti...")
        
        # Pivot per correlazioni
        pivot_data = indicators_df.pivot(index='date', columns='symbol', values='adj_close')
        returns_data = pivot_data.pct_change().dropna()
        
        # Matrice correlazioni
        correlation_matrix = returns_data.corr()
        
        # Trova coppie con alta correlazione
        high_corr_pairs = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                corr = correlation_matrix.iloc[i, j]
                if abs(corr) > 0.7:  # Alta correlazione
                    high_corr_pairs.append((
                        correlation_matrix.columns[i],
                        correlation_matrix.columns[j],
                        corr
                    ))
        
        print(f"📊 Coppie ad alta correlazione (>0.7): {len(high_corr_pairs)}")
        for pair in high_corr_pairs[:5]:  # Prime 5
            print(f"  {pair[0]} ↔ {pair[1]}: {pair[2]:.3f}")
        
        # 4. Analisi stagionalità
        print("\n📅 Analisi stagionalità...")
        
        seasonal_analysis = {}
        for symbol in indicators_df['symbol'].unique():
            symbol_data = indicators_df[indicators_df['symbol'] == symbol]
            
            # Returns mensili per mese
            symbol_data['monthly_return'] = symbol_data['adj_close'].pct_change()
            monthly_returns = symbol_data.groupby('month')['monthly_return'].mean()
            
            seasonal_analysis[symbol] = {
                'best_month': monthly_returns.idxmax(),
                'worst_month': monthly_returns.idxmin(),
                'best_month_return': monthly_returns.max(),
                'worst_month_return': monthly_returns.min(),
                'monthly_volatility': monthly_returns.std()
            }
        
        # 5. Definizione strategie multiple
        print("\n🎯 Definizione strategie multiple...")
        
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
            },
            'seasonal': {
                'name': 'Seasonal Timing',
                'signals': [],
                'performance': []
            },
            'adaptive': {
                'name': 'Adaptive Multi-Strategy',
                'signals': [],
                'performance': []
            }
        }
        
        # 6. Backtest strategie
        print("\n🔄 Backtest strategie multiple...")
        
        for symbol in indicators_df['symbol'].unique():
            symbol_data = indicators_df[indicators_df['symbol'] == symbol].copy()
            symbol_data = symbol_data.dropna()
            
            if len(symbol_data) < 200:  # Minimo 200 giorni
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
                
                if current['rsi'] < 30:  # Oversold
                    mr_signals.append(1)  # BUY
                elif current['rsi'] > 70:  # Overbought
                    mr_signals.append(-1)  # SELL
                else:
                    mr_signals.append(0)  # HOLD
            
            strategies['mean_reversion']['signals'].extend(mr_signals)
            
            # Momentum
            mom_signals = []
            for i in range(252, len(symbol_data)):
                current = symbol_data.iloc[i]
                
                if current['momentum_12m'] > 0.05:  # > 5% annualizzato
                    mom_signals.append(1)  # BUY
                elif current['momentum_12m'] < -0.05:  # < -5% annualizzato
                    mom_signals.append(-1)  # SELL
                else:
                    mom_signals.append(0)  # HOLD
            
            strategies['momentum']['signals'].extend(mom_signals)
            
            # Seasonal
            seasonal = seasonal_analysis[symbol]
            seasonal_signals = []
            
            for i in range(len(symbol_data)):
                current = symbol_data.iloc[i]
                
                # BUY nei mesi migliori, SELL nei mesi peggiori
                if current['month'] == seasonal['best_month']:
                    seasonal_signals.append(1)
                elif current['month'] == seasonal['worst_month']:
                    seasonal_signals.append(-1)
                else:
                    seasonal_signals.append(0)
            
            strategies['seasonal']['signals'].extend(seasonal_signals)
        
        # 7. Calcolo performance strategie
        print("\n📊 Calcolo performance strategie...")
        
        benchmark_returns = returns_data.mean(axis=1)  # Returns media benchmark
        
        for strategy_name, strategy_data in strategies.items():
            if not strategy_data['signals']:
                continue
            
            # Normalizza segnali alla lunghezza dei returns
            min_len = min(len(benchmark_returns), len(strategy_data['signals']))
            strategy_signals = strategy_data['signals'][:min_len]
            benchmark_ret = benchmark_returns.iloc[:min_len]
            
            # Calcola returns strategia
            strategy_returns = []
            for i, signal in enumerate(strategy_signals):
                if signal == 1:  # BUY
                    strategy_returns.append(benchmark_ret.iloc[i])
                elif signal == -1:  # SELL
                    strategy_returns.append(-benchmark_ret.iloc[i])
                else:  # HOLD
                    strategy_returns.append(0)
            
            strategy_returns = pd.Series(strategy_returns)
            
            # Calcola metriche
            cagr = (1 + strategy_returns.mean()) ** 252 - 1
            volatility = strategy_returns.std() * np.sqrt(252)
            sharpe = cagr / volatility if volatility > 0 else 0
            
            # Cumulative returns
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
        
        # 8. Ottimizzazione combinazione strategie
        print("\n🎯 Ottimizzazione combinazione strategie...")
        
        # Machine Learning per pesi ottimali
        best_combination = None
        best_sharpe = -float('inf')
        
        # Prova combinazioni diverse
        strategy_names = list(strategies.keys())
        
        for i in range(len(strategy_names)):
            for j in range(i+1, len(strategy_names)):
                for k in range(j+1, len(strategy_names)):
                    combo = [strategy_names[i], strategy_names[j], strategy_names[k]]
                    
                    # Calcola performance combinazione
                    combo_performance = calculate_combination_performance(
                        strategies, combo, benchmark_returns
                    )
                    
                    if combo_performance['sharpe'] > best_sharpe:
                        best_sharpe = combo_performance['sharpe']
                        best_combination = {
                            'strategies': combo,
                            'performance': combo_performance
                        }
        
        # 9. Regime Detection
        print("\n🌊 Regime Detection...")
        
        # Semplice regime detection basato su volatilità
        volatility_regime = detect_volatility_regime(indicators_df)
        
        # 10. Generazione configurazione ottimale
        print("\n⚙️ Generazione configurazione ottimale...")
        
        optimal_config = {
            'timestamp': datetime.now().isoformat(),
            'benchmark_performance': {
                'cagr': benchmark_returns.mean() * 252,
                'volatility': benchmark_returns.std() * np.sqrt(252),
                'sharpe': benchmark_returns.mean() / (benchmark_returns.std() * np.sqrt(252))
            },
            'best_combination': best_combination,
            'correlation_analysis': {
                'high_correlation_pairs': high_corr_pairs,
                'correlation_matrix': correlation_matrix.to_dict()
            },
            'seasonal_analysis': seasonal_analysis,
            'volatility_regime': volatility_regime,
            'strategy_weights': calculate_optimal_weights(strategies, best_combination)
        }
        
        # 11. Salva configurazione ottimale
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        config_file = os.path.join(reports_dir, f"optimal_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(config_file, 'w') as f:
            json.dump(optimal_config, f, indent=2, default=str)
        
        print(f"📄 Configurazione ottimale salvata: {config_file}")
        
        # 12. Riepilogo risultati
        print(f"\n🎯 RIEPILOGO OTTIMIZZAZIONE:")
        
        if best_combination:
            combo = best_combination
            print(f"🏆 Migliore combinazione ({combo['performance']['sharpe']:.2f} Sharpe):")
            for strategy in combo['strategies']:
                print(f"  • {strategies[strategy]['name']}")
            
            print(f"\n📊 Performance vs Benchmark:")
            print(f"  Strategy CAGR: {combo['performance']['cagr']:.2%}")
            print(f"  Benchmark CAGR: {optimal_config['benchmark_performance']['cagr']:.2%}")
            print(f"  Alpha: {combo['performance']['cagr'] - optimal_config['benchmark_performance']['cagr']:+.2%}")
            print(f"  Strategy Sharpe: {combo['performance']['sharpe']:.2f}")
            print(f"  Benchmark Sharpe: {optimal_config['benchmark_performance']['sharpe']:.2f}")
        
        print(f"\n✅ Ottimizzazione completata")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore ottimizzazione: {e}")
        return False
        
    finally:
        conn.close()

def calculate_combination_performance(strategies, combo, benchmark_returns):
    """Calcola performance combinazione strategie"""
    
    # Pesi uguali per semplicità
    weights = [1/len(combo)] * len(combo)
    
    # Calcola segnali combinati
    min_len = len(benchmark_returns)
    combined_signals = []
    
    for i in range(min_len):
        signal_sum = 0
        for j, strategy_name in enumerate(combo):
            if i < len(strategies[strategy_name]['signals']):
                signal_sum += strategies[strategy_name]['signals'][i] * weights[j]
        
        # Normalizza segnale
        if signal_sum > 0.5:
            combined_signals.append(1)
        elif signal_sum < -0.5:
            combined_signals.append(-1)
        else:
            combined_signals.append(0)
    
    # Calcola returns
    strategy_returns = []
    for i, signal in enumerate(combined_signals):
        if signal == 1:
            strategy_returns.append(benchmark_returns.iloc[i])
        elif signal == -1:
            strategy_returns.append(-benchmark_returns.iloc[i])
        else:
            strategy_returns.append(0)
    
    strategy_returns = pd.Series(strategy_returns)
    
    # Metriche
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

def detect_volatility_regime(df):
    """Detecta regime di volatilità"""
    
    # Calcola volatilità rolling
    df['vol_rolling'] = df.groupby('symbol')['adj_close'].transform(
        lambda x: x.pct_change().rolling(20).std() * np.sqrt(252)
    )
    
    # Classifica regime
    avg_vol = df['vol_rolling'].mean()
    
    regime = {
        'current_volatility': df['vol_rolling'].iloc[-1],
        'average_volatility': avg_vol,
        'regime': 'HIGH_VOL' if df['vol_rolling'].iloc[-1] > avg_vol * 1.2 else 'LOW_VOL',
        'volatility_percentile': (df['vol_rolling'].iloc[-1] / avg_vol - 1) * 100
    }
    
    return regime

def calculate_optimal_weights(strategies, best_combination):
    """Calcola pesi ottimali per strategie"""
    
    if not best_combination:
        return {}
    
    # Per ora pesi uguali, ma qui si può implementare ottimizzazione più complessa
    weights = {}
    for strategy in best_combination['strategies']:
        weights[strategy] = 1.0 / len(best_combination['strategies'])
    
    return weights

if __name__ == "__main__":
    success = auto_strategy_optimizer()
    sys.exit(0 if success else 1)
