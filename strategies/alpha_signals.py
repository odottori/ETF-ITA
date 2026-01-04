#!/usr/bin/env python3
"""
Alpha Signals Module - ETF Italia Project v10
Strategie segnali oggettivi secondo DIPF §4
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class AlphaSignals:
    """Signal Engine per ETF Italia Project"""
    
    def __init__(self, config):
        self.config = config
        self.target_vol = config['settings']['volatility_target']
        self.vol_breaker = config['risk_management']['volatility_breaker']
        self.risk_floor = config['risk_management']['risk_scalar_floor']
    
    def compute_trend_signal(self, price, sma_200):
        """Calcola segnale trend following basato su SMA 200"""
        
        if pd.isna(sma_200):
            return 'HOLD', 1.0, 'NO_SMA_DATA'
        
        # Bande attorno SMA 200
        upper_band = sma_200 * 1.02  # 2% above
        lower_band = sma_200 * 0.98  # 2% below
        
        if price > upper_band:
            return 'RISK_ON', 1.0, 'TREND_UP_SMA200'
        elif price < lower_band:
            return 'RISK_OFF', 0.0, 'TREND_DOWN_SMA200'
        else:
            return 'HOLD', 0.5, 'TREND_NEUTRAL_SMA200'
    
    def compute_volatility_regime(self, volatility):
        """Calcola regime volatilità e adjustment"""
        
        if pd.isna(volatility) or volatility <= 0:
            return 'NEUTRAL', 1.0
        
        if volatility > self.vol_breaker:
            return 'HIGH_VOL', 0.5  # Halve size
        elif volatility < 0.10:
            return 'LOW_VOL', 1.2   # Increase size
        else:
            return 'NEUTRAL', 1.0
    
    def compute_drawdown_protection(self, drawdown_pct, current_signal, current_scalar):
        """Protezione drawdown"""
        
        if pd.isna(drawdown_pct):
            return current_signal, current_scalar, 'NO_DRAWDOWN_DATA'
        
        if drawdown_pct < -0.15:  # 15% drawdown
            return 'RISK_OFF', 0.0, 'DRAWDOWN_PROTECT_15'
        elif drawdown_pct < -0.10:  # 10% drawdown
            if current_signal == 'RISK_ON':
                return current_signal, current_scalar * 0.7, 'DRAWDOWN_ADJUST_10'
        
        return current_signal, current_scalar, 'NO_DRAWDOWN_ADJUST'
    
    def compute_volatility_targeting(self, volatility, current_scalar):
        """Volatility targeting per position sizing"""
        
        if pd.isna(volatility) or volatility <= 0:
            return current_scalar
        
        # Scalar inverso alla volatilità
        vol_scalar = self.target_vol / volatility
        vol_scalar = min(1.0, vol_scalar)  # Cap at 1.0
        vol_scalar = max(self.risk_floor, vol_scalar)  # Floor
        
        return current_scalar * vol_scalar
    
    def compute_spy_guard_adjustment(self, spy_guard_active, current_signal, current_scalar):
        """Aggiustamento Spy Guard"""
        
        if spy_guard_active:
            if current_signal == 'RISK_ON':
                return 'RISK_OFF', 0.0, 'SPY_GUARD_BLOCK'
        
        return current_signal, current_scalar, 'SPY_GUARD_OK'
    
    def generate_signal(self, row, spy_guard_active=False):
        """Genera segnale completo per una riga di dati"""
        
        price = row['adj_close']
        sma_200 = row['sma_200']
        volatility = row['volatility_20d']
        drawdown = row['drawdown_pct']
        
        # 1. Trend signal base
        signal_state, risk_scalar, explain = self.compute_trend_signal(price, sma_200)
        
        # 2. Volatility regime
        regime, vol_adj = self.compute_volatility_regime(volatility)
        risk_scalar *= vol_adj
        explain += f'_VOL_{regime}'
        
        # 3. Drawdown protection
        signal_state, risk_scalar, dd_explain = self.compute_drawdown_protection(drawdown, signal_state, risk_scalar)
        explain += f'_{dd_explain}'
        
        # 4. Volatility targeting
        risk_scalar = self.compute_volatility_targeting(volatility, risk_scalar)
        
        # 5. Spy guard
        signal_state, risk_scalar, spy_explain = self.compute_spy_guard_adjustment(spy_guard_active, signal_state, risk_scalar)
        explain += f'_{spy_explain}'
        
        # Arrotonda e limita
        risk_scalar = round(risk_scalar, 3)
        risk_scalar = max(0.0, min(1.0, risk_scalar))
        
        return {
            'signal_state': signal_state,
            'risk_scalar': risk_scalar,
            'explain_code': explain,
            'regime_filter': regime
        }
