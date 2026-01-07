#!/usr/bin/env python3
"""
POC: Regime-Adaptive vs Fixed Parameters (Synthetic Data)
Dimostra il concetto con dati sintetici realistici
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_manager import get_path_manager


def generate_synthetic_market_data(n_days=1000, seed=42):
    """
    Genera dati di mercato sintetici con 3 regimi distinti
    
    Returns:
        DataFrame con: date, price, volatility, regime
    """
    np.random.seed(seed)
    
    dates = pd.date_range(start='2018-01-01', periods=n_days, freq='D')
    
    # Genera regimi (bull/bear/sideways)
    regime_changes = np.random.choice([200, 250, 300], size=n_days//250)
    regimes = []
    current_regime = 'bull'
    
    for i in range(n_days):
        if i > 0 and i % 250 == 0:
            # Cambia regime ogni ~250 giorni
            current_regime = np.random.choice(['bull', 'bear', 'sideways'])
        regimes.append(current_regime)
    
    # Genera prezzi basati su regime
    prices = [100.0]
    volatilities = []
    
    for i in range(1, n_days):
        regime = regimes[i]
        
        if regime == 'bull':
            # Bull: trend positivo, bassa volatility
            drift = 0.0005  # +0.05% al giorno
            vol = 0.01  # 1% giornaliero
        elif regime == 'bear':
            # Bear: trend negativo, alta volatility
            drift = -0.0003  # -0.03% al giorno
            vol = 0.025  # 2.5% giornaliero
        else:  # sideways
            # Sideways: no trend, media volatility
            drift = 0.0
            vol = 0.015  # 1.5% giornaliero
        
        # Random walk con drift
        change = drift + vol * np.random.randn()
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
        
        # Volatility annualizzata
        vol_annual = vol * np.sqrt(252)
        volatilities.append(vol_annual)
    
    volatilities.insert(0, 0.15)  # Primo giorno
    
    df = pd.DataFrame({
        'date': dates,
        'price': prices,
        'volatility': volatilities,
        'regime': regimes
    })
    
    return df


def simulate_trading_strategy(market_data, score_entry_min=0.7, stop_loss=-0.15, 
                               risk_scalar_high_vol=1.0):
    """
    Simula strategia di trading
    
    Args:
        market_data: DataFrame con prezzi e volatility
        score_entry_min: Soglia minima momentum per entry
        stop_loss: Stop loss %
        risk_scalar_high_vol: Riduzione esposizione in alta volatility (1.0 = nessuna riduzione)
    
    Returns:
        Lista di trade con return
    """
    
    trades = []
    position = None
    
    for i in range(20, len(market_data)):
        current = market_data.iloc[i]
        
        # Calcola momentum score (semplificato)
        price_20d_ago = market_data.iloc[i-20]['price']
        momentum = (current['price'] - price_20d_ago) / price_20d_ago
        momentum_score = min(max(momentum * 10, 0), 1)  # Normalizza 0-1
        
        # Entry signal
        if position is None and momentum_score >= score_entry_min:
            # Determina size basato su volatility
            if current['volatility'] > 0.20:
                size = risk_scalar_high_vol  # Ridotto in alta vol
            else:
                size = 1.0
            
            position = {
                'entry_date': current['date'],
                'entry_price': current['price'],
                'entry_volatility': current['volatility'],
                'entry_regime': current['regime'],
                'size': size,
                'momentum_score': momentum_score
            }
        
        # Exit signal (stop-loss o take-profit)
        elif position is not None:
            current_return = (current['price'] - position['entry_price']) / position['entry_price']
            
            # Stop-loss
            if current_return <= stop_loss:
                trade_return = current_return * position['size']
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': current['date'],
                    'entry_regime': position['entry_regime'],
                    'entry_volatility': position['entry_volatility'],
                    'trade_return': trade_return,
                    'exit_reason': 'STOP_LOSS',
                    'size': position['size']
                })
                position = None
            
            # Take-profit (semplificato: +10%)
            elif current_return >= 0.10:
                trade_return = current_return * position['size']
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': current['date'],
                    'entry_regime': position['entry_regime'],
                    'entry_volatility': position['entry_volatility'],
                    'trade_return': trade_return,
                    'exit_reason': 'TAKE_PROFIT',
                    'size': position['size']
                })
                position = None
    
    return pd.DataFrame(trades)


def run_poc_synthetic():
    """
    Esegue POC con dati sintetici
    """
    
    print("\n" + "=" * 80)
    print("POC: REGIME-ADAPTIVE vs FIXED PARAMETERS (Synthetic Data)")
    print("=" * 80 + "\n")
    
    # Genera dati sintetici
    print("📊 Generazione dati sintetici...")
    market_data = generate_synthetic_market_data(n_days=1000)
    print(f"   Generati {len(market_data)} giorni di dati\n")
    
    # Distribuzione regimi
    regime_counts = market_data['regime'].value_counts()
    print("   Distribuzione regimi:")
    for regime, count in regime_counts.items():
        pct = count / len(market_data) * 100
        print(f"   - {regime:10s}: {count:4d} giorni ({pct:5.1f}%)")
    print()
    
    # Metriche per regime
    print("   Metriche medie per regime:")
    for regime in ['bull', 'bear', 'sideways']:
        regime_data = market_data[market_data['regime'] == regime]
        if len(regime_data) > 0:
            avg_vol = regime_data['volatility'].mean()
            print(f"   - {regime:10s}: volatility={avg_vol*100:5.1f}%")
    print()
    
    # Strategia FIXED: parametri uguali per tutti i regimi
    print("🔧 Test 1: STRATEGIA FIXED (parametri fissi)")
    print("   score_entry_min=0.7, stop_loss=-0.15, risk_scalar=1.0\n")
    
    trades_fixed = simulate_trading_strategy(
        market_data,
        score_entry_min=0.7,
        stop_loss=-0.15,
        risk_scalar_high_vol=1.0  # Nessuna riduzione
    )
    
    if len(trades_fixed) == 0:
        print("   ❌ Nessun trade generato\n")
        return None
    
    sharpe_fixed = (trades_fixed['trade_return'].mean() / trades_fixed['trade_return'].std() * np.sqrt(252)) if trades_fixed['trade_return'].std() > 0 else 0
    total_return_fixed = trades_fixed['trade_return'].sum()
    win_rate_fixed = len(trades_fixed[trades_fixed['trade_return'] > 0]) / len(trades_fixed)
    
    print(f"   Trade totali:    {len(trades_fixed)}")
    print(f"   Return totale:   {total_return_fixed*100:+.2f}%")
    print(f"   Return medio:    {trades_fixed['trade_return'].mean()*100:+.2f}%")
    print(f"   Win rate:        {win_rate_fixed*100:.1f}%")
    print(f"   Sharpe:          {sharpe_fixed:.3f}")
    print()
    
    # Strategia ADAPTIVE: riduce esposizione in alta volatility
    print("🔧 Test 2: STRATEGIA ADAPTIVE (risk scalar adattivo)")
    print("   score_entry_min=0.7, stop_loss=-0.15, risk_scalar=0.5 (alta vol)\n")
    
    trades_adaptive = simulate_trading_strategy(
        market_data,
        score_entry_min=0.7,
        stop_loss=-0.15,
        risk_scalar_high_vol=0.5  # Riduzione 50% in alta vol
    )
    
    sharpe_adaptive = (trades_adaptive['trade_return'].mean() / trades_adaptive['trade_return'].std() * np.sqrt(252)) if trades_adaptive['trade_return'].std() > 0 else 0
    total_return_adaptive = trades_adaptive['trade_return'].sum()
    win_rate_adaptive = len(trades_adaptive[trades_adaptive['trade_return'] > 0]) / len(trades_adaptive)
    
    print(f"   Trade totali:    {len(trades_adaptive)}")
    print(f"   Return totale:   {total_return_adaptive*100:+.2f}%")
    print(f"   Return medio:    {trades_adaptive['trade_return'].mean()*100:+.2f}%")
    print(f"   Win rate:        {win_rate_adaptive*100:.1f}%")
    print(f"   Sharpe:          {sharpe_adaptive:.3f}")
    print()
    
    # Analisi per regime
    print("=" * 80)
    print("ANALISI PER REGIME")
    print("=" * 80 + "\n")
    
    print("📊 FIXED Strategy:")
    for regime in ['bull', 'bear', 'sideways']:
        regime_trades = trades_fixed[trades_fixed['entry_regime'] == regime]
        if len(regime_trades) > 0:
            avg_return = regime_trades['trade_return'].mean()
            win_rate = len(regime_trades[regime_trades['trade_return'] > 0]) / len(regime_trades)
            print(f"   {regime:10s}: {len(regime_trades):3d} trade, return={avg_return*100:+6.2f}%, win={win_rate*100:5.1f}%")
    print()
    
    print("📊 ADAPTIVE Strategy:")
    for regime in ['bull', 'bear', 'sideways']:
        regime_trades = trades_adaptive[trades_adaptive['entry_regime'] == regime]
        if len(regime_trades) > 0:
            avg_return = regime_trades['trade_return'].mean()
            win_rate = len(regime_trades[regime_trades['trade_return'] > 0]) / len(regime_trades)
            print(f"   {regime:10s}: {len(regime_trades):3d} trade, return={avg_return*100:+6.2f}%, win={win_rate*100:5.1f}%")
    print()
    
    # Verdict
    print("=" * 80)
    print("VERDICT")
    print("=" * 80 + "\n")
    
    improvement_return = total_return_adaptive - total_return_fixed
    improvement_sharpe = sharpe_adaptive - sharpe_fixed
    
    print(f"   Return Fixed:     {total_return_fixed*100:+.2f}%")
    print(f"   Return Adaptive:  {total_return_adaptive*100:+.2f}%")
    print(f"   Δ Return:         {improvement_return*100:+.2f}%")
    print()
    print(f"   Sharpe Fixed:     {sharpe_fixed:.3f}")
    print(f"   Sharpe Adaptive:  {sharpe_adaptive:.3f}")
    print(f"   Δ Sharpe:         {improvement_sharpe:+.3f}")
    print()
    
    # Analisi drawdown
    print("   📉 Drawdown Analysis:")
    max_dd_fixed = trades_fixed['trade_return'].min()
    max_dd_adaptive = trades_adaptive['trade_return'].min()
    print(f"   Max DD Fixed:     {max_dd_fixed*100:.2f}%")
    print(f"   Max DD Adaptive:  {max_dd_adaptive*100:.2f}%")
    print(f"   Δ Max DD:         {(max_dd_adaptive - max_dd_fixed)*100:+.2f}%")
    print()
    
    if improvement_sharpe > 0.2:
        print("   ✅ ADAPTIVE VINCE: Miglioramento significativo (>0.2 Sharpe)")
        print("   → Vale la pena implementare regime-adaptive system")
        print()
        print("   💡 INSIGHT: Ridurre esposizione in alta volatility protegge il capitale")
        print("      e migliora risk-adjusted returns. Il sistema 'impara' a essere")
        print("      più conservativo quando il mercato è instabile.")
        recommendation = "IMPLEMENT_ADAPTIVE"
    elif improvement_sharpe > 0:
        print("   ⚠️  ADAPTIVE MARGINALE: Miglioramento modesto (<0.2 Sharpe)")
        print("   → Valutare se complessità vale il guadagno")
        print()
        print("   💡 INSIGHT: Adaptive aiuta ma il guadagno è limitato.")
        print("      Potrebbe non valere la complessità aggiuntiva.")
        recommendation = "EVALUATE"
    else:
        print("   ❌ FIXED VINCE: Parametri fissi sufficienti")
        print("   → Non serve complessità aggiuntiva")
        print()
        print("   💡 INSIGHT: In questo scenario, parametri fissi sono robusti.")
        print("      Adaptive non aggiunge valore significativo.")
        recommendation = "KEEP_FIXED"
    
    print()
    
    # Salva risultati
    pm = get_path_manager()
    output_dir = Path(pm.get_path('reports'))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Salva trade
    trades_fixed['strategy'] = 'FIXED'
    trades_adaptive['strategy'] = 'ADAPTIVE'
    all_trades = pd.concat([trades_fixed, trades_adaptive])
    
    trades_path = output_dir / f'poc_synthetic_trades_{timestamp}.csv'
    all_trades.to_csv(trades_path, index=False)
    print(f"💾 Trade salvati: {trades_path}")
    
    # Salva market data
    market_path = output_dir / f'poc_synthetic_market_{timestamp}.csv'
    market_data.to_csv(market_path, index=False)
    print(f"💾 Market data salvati: {market_path}")
    
    return {
        'recommendation': recommendation,
        'sharpe_fixed': sharpe_fixed,
        'sharpe_adaptive': sharpe_adaptive,
        'improvement_sharpe': improvement_sharpe,
        'improvement_return': improvement_return
    }


if __name__ == '__main__':
    results = run_poc_synthetic()
    
    if results:
        print("\n✅ POC completato con successo")
        print(f"\n🎯 Raccomandazione finale: {results['recommendation']}")
        
        if results['recommendation'] == 'IMPLEMENT_ADAPTIVE':
            print("\n📋 NEXT STEPS:")
            print("   1. Implementare regime_classifier.py")
            print("   2. Estendere backtest_engine con parameter_optimizer.py")
            print("   3. Modificare strategy_engine per usare parametri adattivi")
            print("   4. Test su dati reali storici (2018-2025)")
    else:
        print("\n❌ POC fallito")
        sys.exit(1)
