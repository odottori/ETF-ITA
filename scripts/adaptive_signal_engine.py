#!/usr/bin/env python3
"""
Adaptive Signal Engine - ETF Italia Project v10
Motore segnali adattivo con regime detection e ottimizzazione automatica
"""

import sys
import os
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def adaptive_signal_engine():
    """Motore segnali adattivo con machine learning"""
    
    print("🤖 ADAPTIVE SIGNAL ENGINE - ETF Italia Project v10")
    print("=" * 70)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        print("🔍 Inizio motore segnali adattivo...")
        
        # 1. Carica dati storici completi
        print("\n📊 Caricamento dati storici per training...")
        
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
        
        # 2. Calcola feature engineering avanzata
        print("\n🔬 Feature engineering avanzata...")
        
        features_data = []
        
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol].copy().sort_values('date')
            
            # Price features
            symbol_data['returns_1d'] = symbol_data['adj_close'].pct_change()
            symbol_data['returns_5d'] = symbol_data['adj_close'].pct_change(5)
            symbol_data['returns_20d'] = symbol_data['adj_close'].pct_change(20)
            
            # Moving averages
            symbol_data['sma_10'] = symbol_data['adj_close'].rolling(10).mean()
            symbol_data['sma_20'] = symbol_data['adj_close'].rolling(20).mean()
            symbol_data['sma_50'] = symbol_data['adj_close'].rolling(50).mean()
            symbol_data['sma_200'] = symbol_data['adj_close'].rolling(200).mean()
            
            # Exponential moving averages
            symbol_data['ema_12'] = symbol_data['adj_close'].ewm(span=12).mean()
            symbol_data['ema_26'] = symbol_data['adj_close'].ewm(span=26).mean()
            
            # MACD
            symbol_data['macd'] = symbol_data['ema_12'] - symbol_data['ema_26']
            symbol_data['macd_signal'] = symbol_data['macd'].ewm(span=9).mean()
            symbol_data['macd_histogram'] = symbol_data['macd'] - symbol_data['macd_signal']
            
            # RSI
            delta = symbol_data['adj_close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            symbol_data['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            bb_period = 20
            bb_std = symbol_data['adj_close'].rolling(bb_period).std()
            bb_middle = symbol_data['sma_20']
            symbol_data['bb_upper'] = bb_middle + (bb_std * 2)
            symbol_data['bb_lower'] = bb_middle - (bb_std * 2)
            symbol_data['bb_position'] = (symbol_data['adj_close'] - symbol_data['bb_lower']) / (symbol_data['bb_upper'] - symbol_data['bb_lower'])
            
            # Stochastic Oscillator
            stoch_period = 14
            low_min = symbol_data['low'].rolling(stoch_period).min()
            high_max = symbol_data['high'].rolling(stoch_period).max()
            symbol_data['stoch_k'] = 100 * (symbol_data['adj_close'] - low_min) / (high_max - low_min)
            symbol_data['stoch_d'] = symbol_data['stoch_k'].rolling(3).mean()
            
            # Volatility features
            symbol_data['volatility_5d'] = symbol_data['returns_1d'].rolling(5).std() * np.sqrt(252)
            symbol_data['volatility_20d'] = symbol_data['returns_1d'].rolling(20).std() * np.sqrt(252)
            symbol_data['volatility_ratio'] = symbol_data['volatility_5d'] / symbol_data['volatility_20d']
            
            # Volume features
            symbol_data['volume_sma'] = symbol_data['volume'].rolling(20).mean()
            symbol_data['volume_ratio'] = symbol_data['volume'] / symbol_data['volume_sma']
            
            # Price patterns
            symbol_data['higher_high'] = symbol_data['high'] > symbol_data['high'].shift(1)
            symbol_data['lower_low'] = symbol_data['low'] < symbol_data['low'].shift(1)
            
            # Momentum features
            symbol_data['momentum_1m'] = symbol_data['adj_close'] / symbol_data['adj_close'].shift(21) - 1
            symbol_data['momentum_3m'] = symbol_data['adj_close'] / symbol_data['adj_close'].shift(63) - 1
            symbol_data['momentum_6m'] = symbol_data['adj_close'] / symbol_data['adj_close'].shift(126) - 1
            symbol_data['momentum_12m'] = symbol_data['adj_close'] / symbol_data['adj_close'].shift(252) - 1
            
            # Seasonal features
            symbol_data['month'] = symbol_data['date'].dt.month
            symbol_data['day_of_week'] = symbol_data['date'].dt.dayofweek
            symbol_data['quarter'] = symbol_data['date'].dt.quarter
            
            # Regime features
            symbol_data['price_sma200_ratio'] = symbol_data['adj_close'] / symbol_data['sma_200']
            symbol_data['volume_price_trend'] = np.sign(symbol_data['volume_ratio'] * symbol_data['returns_5d'])
            
            features_data.append(symbol_data)
        
        features_df = pd.concat(features_data, ignore_index=True)
        
        # 3. Regime Detection
        print("\n🌊 Regime Detection...")
        
        regime_labels = detect_market_regimes(features_df)
        
        # 4. Feature Selection
        print("\n🎯 Feature Selection...")
        
        feature_columns = [
            'returns_1d', 'returns_5d', 'returns_20d',
            'sma_10', 'sma_20', 'sma_50', 'sma_200',
            'ema_12', 'ema_26',
            'macd', 'macd_signal', 'macd_histogram',
            'rsi',
            'bb_position',
            'stoch_k', 'stoch_d',
            'volatility_5d', 'volatility_20d', 'volatility_ratio',
            'volume_ratio',
            'higher_high', 'lower_low',
            'momentum_1m', 'momentum_3m', 'momentum_6m', 'momentum_12m',
            'price_sma200_ratio',
            'month', 'day_of_week', 'quarter'
        ]
        
        # 5. Training Data Preparation
        print("\n🎓 Training Data Preparation...")
        
        # Create target variables (future returns)
        for symbol in features_df['symbol'].unique():
            mask = features_df['symbol'] == symbol
            features_df.loc[mask, 'future_return_5d'] = features_df.loc[mask, 'adj_close'].shift(-5) / features_df.loc[mask, 'adj_close'] - 1
            features_df.loc[mask, 'future_return_20d'] = features_df.loc[mask, 'adj_close'].shift(-20) / features_df.loc[mask, 'adj_close'] - 1
        
        # Remove NaN values
        training_data = features_df.dropna(subset=feature_columns + ['future_return_5d', 'future_return_20d'])
        
        # 6. Model Training per Regime
        print("\n🤖 Training Models per Regime...")
        
        models = {}
        scalers = {}
        
        for regime in regime_labels['regime'].unique():
            if pd.isna(regime):
                continue
                
            regime_data = training_data[training_data['regime'] == regime]
            
            if len(regime_data) < 100:
                continue
            
            X = regime_data[feature_columns]
            y_5d = (regime_data['future_return_5d'] > 0.02).astype(int)  # 2% threshold
            y_20d = (regime_data['future_return_20d'] > 0.05).astype(int)  # 5% threshold
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train models
            model_5d = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
            model_20d = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
            
            model_5d.fit(X_scaled, y_5d)
            model_20d.fit(X_scaled, y_20d)
            
            models[regime] = {
                'model_5d': model_5d,
                'model_20d': model_20d,
                'scaler': scaler,
                'feature_importance': dict(zip(feature_columns, model_5d.feature_importances_))
            }
            
            scalers[regime] = scaler
            
            print(f"✅ Trained model for regime: {regime}")
        
        # 7. Generate Adaptive Signals
        print("\n📈 Generating Adaptive Signals...")
        
        current_date = datetime.now().date()
        
        # Get current market data
        current_data = conn.execute("""
        SELECT symbol, date, adj_close, volume, high, low, open
        FROM market_data
        WHERE date >= ? - INTERVAL '30 days'
        ORDER BY symbol, date
        """, [current_date]).fetchall()
        
        if not current_data:
            print("❌ Nessun dato recente disponibile")
            return False
        
        current_df = pd.DataFrame(current_data, columns=['symbol', 'date', 'adj_close', 'volume', 'high', 'low', 'open'])
        current_df['date'] = pd.to_datetime(current_df['date'])
        
        # Calculate features for current data
        current_features = []
        
        for symbol in current_df['symbol'].unique():
            symbol_data = current_df[current_df['symbol'] == symbol].copy().sort_values('date')
            
            # Calculate same features as training
            symbol_data['returns_1d'] = symbol_data['adj_close'].pct_change()
            symbol_data['sma_10'] = symbol_data['adj_close'].rolling(10).mean()
            symbol_data['sma_20'] = symbol_data['adj_close'].rolling(20).mean()
            symbol_data['sma_50'] = symbol_data['adj_close'].rolling(50).mean()
            symbol_data['sma_200'] = symbol_data['adj_close'].rolling(200).mean()
            symbol_data['ema_12'] = symbol_data['adj_close'].ewm(span=12).mean()
            symbol_data['ema_26'] = symbol_data['adj_close'].ewm(span=26).mean()
            symbol_data['macd'] = symbol_data['ema_12'] - symbol_data['ema_26']
            symbol_data['rsi'] = 100 - (100 / (1 + (symbol_data['adj_close'].diff().where(lambda x: x > 0, 0).rolling(14).mean() / (-symbol_data['adj_close'].diff().where(lambda x: x < 0, 0)).rolling(14).mean())))
            symbol_data['volatility_20d'] = symbol_data['returns_1d'].rolling(20).std() * np.sqrt(252)
            symbol_data['price_sma200_ratio'] = symbol_data['adj_close'] / symbol_data['sma_200']
            symbol_data['month'] = symbol_data['date'].dt.month
            symbol_data['day_of_week'] = symbol_data['date'].dt.dayofweek
            
            # Add other required features with defaults
            for col in feature_columns:
                if col not in symbol_data.columns:
                    symbol_data[col] = 0
            
            current_features.append(symbol_data)
        
        current_features_df = pd.concat(current_features, ignore_index=True)
        
        # 8. Generate Signals
        adaptive_signals = []
        
        for symbol in current_features_df['symbol'].unique():
            symbol_data = current_features_df[current_features_df['symbol'] == symbol].iloc[-1]  # Latest data
            
            # Detect current regime
            current_regime = detect_current_regime(symbol_data, regime_labels)
            
            if current_regime not in models:
                print(f"⚠️ No model for regime: {current_regime} - using default")
                continue
            
            # Prepare features
            X_current = symbol_data[feature_columns].values.reshape(1, -1)
            X_scaled = scalers[current_regime].transform(X_current)
            
            # Get predictions
            prob_5d = models[current_regime]['model_5d'].predict_proba(X_scaled)[0][1]
            prob_20d = models[current_regime]['model_20d'].predict_proba(X_scaled)[0][1]
            
            # Generate signal
            if prob_5d > 0.6 and prob_20d > 0.6:
                signal_state = 'RISK_ON'
                risk_scalar = min(1.0, (prob_5d + prob_20d) / 2)
            elif prob_5d < 0.4 and prob_20d < 0.4:
                signal_state = 'RISK_OFF'
                risk_scalar = max(0.0, (prob_5d + prob_20d) / 2 - 0.5)
            else:
                signal_state = 'HOLD'
                risk_scalar = 0.5
            
            # Explain code
            explain_code = f"Regime: {current_regime}, 5d: {prob_5d:.2f}, 20d: {prob_20d:.2f}"
            
            adaptive_signals.append({
                'symbol': symbol,
                'date': current_date,
                'signal_state': signal_state,
                'risk_scalar': risk_scalar,
                'explain_code': explain_code,
                'regime': current_regime,
                'prob_5d': prob_5d,
                'prob_20d': prob_20d
            })
        
        # 9. Save Adaptive Signals
        print("\n💾 Saving Adaptive Signals...")
        
        # Clear existing signals
        conn.execute("DELETE FROM signals WHERE date >= ?", [current_date])
        
        # Insert new signals
        for signal in adaptive_signals:
            conn.execute("""
            INSERT INTO signals (date, symbol, signal_state, risk_scalar, explain_code, sma_200, volatility_20d, spy_guard, regime_filter, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                signal['date'],
                signal['symbol'],
                signal['signal_state'],
                signal['risk_scalar'],
                signal['explain_code'],
                symbol_data.get('sma_200', 0),
                symbol_data.get('volatility_20d', 0),
                False,  # TODO: implement spy guard
                signal['regime'],
                datetime.now()
            ])
        
        print(f"✅ Generated {len(adaptive_signals)} adaptive signals")
        
        # 10. Save Models
        print("\n💾 Saving Adaptive Models...")
        
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        os.makedirs(models_dir, exist_ok=True)
        
        # Save models and scalers
        import pickle
        
        for regime, model_data in models.items():
            model_file = os.path.join(models_dir, f"model_{regime}.pkl")
            scaler_file = os.path.join(models_dir, f"scaler_{regime}.pkl")
            
            with open(model_file, 'wb') as f:
                pickle.dump(model_data['model_5d'], f)
            
            with open(scaler_file, 'wb') as f:
                pickle.dump(model_data['scaler'], f)
        
        # Save feature importance
        feature_importance_file = os.path.join(models_dir, "feature_importance.json")
        with open(feature_importance_file, 'w') as f:
            json.dump({regime: data['feature_importance'] for regime, data in models.items()}, f, indent=2)
        
        print(f"✅ Models saved to {models_dir}")
        
        # 11. Summary
        print(f"\n📊 ADAPTIVE SIGNAL ENGINE SUMMARY:")
        print(f"Regimes detected: {len(models)}")
        print(f"Features used: {len(feature_columns)}")
        print(f"Signals generated: {len(adaptive_signals)}")
        
        signal_summary = pd.DataFrame(adaptive_signals)
        print(f"\nSignal distribution:")
        print(signal_summary['signal_state'].value_counts())
        
        print(f"\nRegime distribution:")
        print(signal_summary['regime'].value_counts())
        
        print(f"\n✅ Adaptive Signal Engine completed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore adaptive signal engine: {e}")
        return False
        
    finally:
        conn.close()

def detect_market_regimes(df):
    """Detect market regimes based on volatility and trend"""
    
    # Calculate market-wide volatility
    market_vol = df.groupby('date')['returns_1d'].std().mean() * np.sqrt(252)
    market_vol = market_vol.to_dict()
    
    # Calculate market-wide trend
    market_trend = df.groupby('date')['price_sma200_ratio'].mean()
    market_trend = market_trend.to_dict()
    
    # Define regimes
    regimes = []
    
    for date in df['date'].unique():
        date_vol = market_vol.get(date, 0)
        date_trend = market_trend.get(date, 1)
        
        if date_vol > 0.25:  # High volatility
            if date_trend < 0.9:  # Bear market
                regime = 'BEAR_HIGH_VOL'
            else:
                regime = 'BULL_HIGH_VOL'
        elif date_vol < 0.15:  # Low volatility
            if date_trend > 1.1:  # Strong bull
                regime = 'BULL_LOW_VOL'
            else:
                regime = 'SIDEWAYS_LOW_VOL'
        else:  # Normal volatility
            if date_trend > 1.05:
                regime = 'BULL_NORMAL'
            elif date_trend < 0.95:
                regime = 'BEAR_NORMAL'
            else:
                regime = 'SIDEWAYS_NORMAL'
        
        regimes.append({'date': date, 'regime': regime})
    
    return pd.DataFrame(regimes)

def detect_current_regime(current_data, regime_labels):
    """Detect current regime for a symbol"""
    
    # Simple heuristic based on volatility and trend
    volatility = current_data.get('volatility_20d', 0.15)
    trend_ratio = current_data.get('price_sma200_ratio', 1.0)
    
    if volatility > 0.25:
        return 'BEAR_HIGH_VOL' if trend_ratio < 0.9 else 'BULL_HIGH_VOL'
    elif volatility < 0.15:
        return 'BULL_LOW_VOL' if trend_ratio > 1.1 else 'SIDEWAYS_LOW_VOL'
    else:
        return 'BULL_NORMAL' if trend_ratio > 1.05 else 'SIDEWAYS_NORMAL'

if __name__ == "__main__":
    success = adaptive_signal_engine()
    sys.exit(0 if success else 1)
