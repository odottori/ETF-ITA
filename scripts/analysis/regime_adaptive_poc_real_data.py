#!/usr/bin/env python3
"""
POC: Regime-Adaptive vs Fixed Parameters (Real Market Data)
Analizza dati storici reali da market_data e simula strategie
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_manager import get_path_manager


def classify_regime_from_metrics(volatility: float, trend: float) -> str:
    """
    Classifica regime basato su volatility e trend osservabili
    
    Args:
        volatility: Volatilità annualizzata (0.15 = 15%)
        trend: Return ultimi 50 giorni
    
    Returns:
        "bull", "bear", "sideways"
    """
    if trend > 0.05 and volatility < 0.20:
        return "bull"
    elif trend < -0.05 or volatility > 0.25:
        return "bear"
    else:
        return "sideways"


def get_historical_data_with_regime(conn, symbol: str, start_date: str, end_date: str):
    """
    Recupera dati storici e calcola regime per ogni giorno
    """
    
    query = """
    WITH daily_data AS (
        SELECT 
            date,
            symbol,
            adj_close,
            close,
            volume,
            -- Volatility ultimi 20 giorni
            STDDEV(adj_close) OVER (
                PARTITION BY symbol 
                ORDER BY date 
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) / AVG(adj_close) OVER (
                PARTITION BY symbol 
                ORDER BY date 
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) * SQRT(252) as volatility,
            -- Trend ultimi 50 giorni
            (adj_close - LAG(adj_close, 50) OVER (PARTITION BY symbol ORDER BY date)) 
            / LAG(adj_close, 50) OVER (PARTITION BY symbol ORDER BY date) as trend_50d,
            -- Momentum 20 giorni per entry signal
            (adj_close - LAG(adj_close, 20) OVER (PARTITION BY symbol ORDER BY date)) 
            / LAG(adj_close, 20) OVER (PARTITION BY symbol ORDER BY date) as momentum_20d
        FROM market_data
        WHERE symbol = ?
        AND date BETWEEN ? AND ?
    )
    SELECT 
        date,
        adj_close,
        close,
        volume,
        COALESCE(volatility, 0.15) as volatility,
        COALESCE(trend_50d, 0.0) as trend,
        COALESCE(momentum_20d, 0.0) as momentum
    FROM daily_data
    WHERE date >= ?
    ORDER BY date
    """
    
    # Start 50 giorni prima per avere dati completi
    extended_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=50)).strftime('%Y-%m-%d')
    
    df = conn.execute(query, [symbol, extended_start, end_date, start_date]).fetchdf()
    
    if len(df) == 0:
        return None
    
    # Classifica regime
    df['regime'] = df.apply(
        lambda row: classify_regime_from_metrics(row['volatility'], row['trend']),
        axis=1
    )
    
    return df


def simulate_strategy_on_real_data(df, score_entry_min=0.7, stop_loss=-0.15, 
                                    risk_scalar_by_regime=None):
    """
    Simula strategia su dati reali
    
    Args:
        df: DataFrame con dati storici e regime
        score_entry_min: Soglia minima momentum per entry
        stop_loss: Stop loss %
        risk_scalar_by_regime: Dict con risk scalar per regime (None = 1.0 per tutti)
    
    Returns:
        DataFrame con trade
    """
    
    if risk_scalar_by_regime is None:
        risk_scalar_by_regime = {'bull': 1.0, 'bear': 1.0, 'sideways': 1.0}
    
    trades = []
    position = None
    
    for i in range(len(df)):
        current = df.iloc[i]
        
        # Normalizza momentum a score 0-1
        momentum_score = min(max(current['momentum'] * 5 + 0.5, 0), 1)
        
        # Entry signal
        if position is None and momentum_score >= score_entry_min:
            # Determina size basato su regime
            regime = current['regime']
            size = risk_scalar_by_regime.get(regime, 1.0)
            
            position = {
                'entry_date': current['date'],
                'entry_price': current['close'],
                'entry_volatility': current['volatility'],
                'entry_regime': regime,
                'size': size,
                'momentum_score': momentum_score
            }
        
        # Exit signal
        elif position is not None:
            current_return = (current['close'] - position['entry_price']) / position['entry_price']
            
            # Stop-loss
            if current_return <= stop_loss:
                trade_return = current_return * position['size']
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': current['date'],
                    'entry_price': position['entry_price'],
                    'exit_price': current['close'],
                    'entry_regime': position['entry_regime'],
                    'entry_volatility': position['entry_volatility'],
                    'trade_return': trade_return,
                    'raw_return': current_return,
                    'exit_reason': 'STOP_LOSS',
                    'size': position['size'],
                    'holding_days': (current['date'] - position['entry_date']).days
                })
                position = None
            
            # Take-profit (+15%)
            elif current_return >= 0.15:
                trade_return = current_return * position['size']
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': current['date'],
                    'entry_price': position['entry_price'],
                    'exit_price': current['close'],
                    'entry_regime': position['entry_regime'],
                    'entry_volatility': position['entry_volatility'],
                    'trade_return': trade_return,
                    'raw_return': current_return,
                    'exit_reason': 'TAKE_PROFIT',
                    'size': position['size'],
                    'holding_days': (current['date'] - position['entry_date']).days
                })
                position = None
    
    # Close final position
    if position is not None:
        final = df.iloc[-1]
        current_return = (final['close'] - position['entry_price']) / position['entry_price']
        trade_return = current_return * position['size']
        trades.append({
            'entry_date': position['entry_date'],
            'exit_date': final['date'],
            'entry_price': position['entry_price'],
            'exit_price': final['close'],
            'entry_regime': position['entry_regime'],
            'entry_volatility': position['entry_volatility'],
            'trade_return': trade_return,
            'raw_return': current_return,
            'exit_reason': 'END_PERIOD',
            'size': position['size'],
            'holding_days': (final['date'] - position['entry_date']).days
        })
    
    return pd.DataFrame(trades)


def run_poc_real_data(symbol='VWCE.MI', start_date='2020-01-01', end_date='2025-01-01'):
    """
    Esegue POC con dati reali da market_data
    """
    
    pm = get_path_manager()
    db_path = str(pm.db_path)
    conn = duckdb.connect(db_path, read_only=True)
    
    print("\n" + "=" * 80)
    print("POC: REGIME-ADAPTIVE vs FIXED PARAMETERS (Real Market Data)")
    print("=" * 80 + "\n")
    print(f"Simbolo: {symbol}")
    print(f"Periodo: {start_date} → {end_date}\n")
    
    # Recupera dati storici
    print("📊 Caricamento dati storici...")
    df = get_historical_data_with_regime(conn, symbol, start_date, end_date)
    
    if df is None or len(df) == 0:
        print(f"❌ Nessun dato trovato per {symbol} nel periodo specificato")
        conn.close()
        return None
    
    print(f"   Caricati {len(df)} giorni di dati\n")
    
    # Distribuzione regimi
    regime_counts = df['regime'].value_counts()
    print("   Distribuzione regimi:")
    for regime, count in regime_counts.items():
        pct = count / len(df) * 100
        print(f"   - {regime:10s}: {count:4d} giorni ({pct:5.1f}%)")
    print()
    
    # Metriche per regime
    print("   Metriche medie per regime:")
    for regime in ['bull', 'bear', 'sideways']:
        regime_data = df[df['regime'] == regime]
        if len(regime_data) > 0:
            avg_vol = regime_data['volatility'].mean()
            avg_trend = regime_data['trend'].mean()
            print(f"   - {regime:10s}: vol={avg_vol*100:5.1f}%, trend={avg_trend*100:+6.2f}%")
    print()
    
    # Strategia FIXED
    print("🔧 Test 1: STRATEGIA FIXED")
    print("   Parametri: score_entry=0.7, stop_loss=-0.15, risk_scalar=1.0 (tutti regimi)\n")
    
    trades_fixed = simulate_strategy_on_real_data(
        df,
        score_entry_min=0.7,
        stop_loss=-0.15,
        risk_scalar_by_regime={'bull': 1.0, 'bear': 1.0, 'sideways': 1.0}
    )
    
    if len(trades_fixed) == 0:
        print("   ⚠️  Nessun trade generato con parametri fixed\n")
        conn.close()
        return None
    
    sharpe_fixed = (trades_fixed['trade_return'].mean() / trades_fixed['trade_return'].std() * np.sqrt(252)) if trades_fixed['trade_return'].std() > 0 else 0
    total_return_fixed = trades_fixed['trade_return'].sum()
    win_rate_fixed = len(trades_fixed[trades_fixed['trade_return'] > 0]) / len(trades_fixed)
    avg_holding_fixed = trades_fixed['holding_days'].mean()
    
    print(f"   Trade totali:       {len(trades_fixed)}")
    print(f"   Return totale:      {total_return_fixed*100:+.2f}%")
    print(f"   Return medio:       {trades_fixed['trade_return'].mean()*100:+.2f}%")
    print(f"   Win rate:           {win_rate_fixed*100:.1f}%")
    print(f"   Sharpe:             {sharpe_fixed:.3f}")
    print(f"   Holding medio:      {avg_holding_fixed:.0f} giorni")
    print()
    
    # Strategia ADAPTIVE
    print("🔧 Test 2: STRATEGIA ADAPTIVE")
    print("   Parametri: score_entry=0.7, stop_loss=-0.15")
    print("   Risk scalar: bull=1.0, sideways=0.8, bear=0.5\n")
    
    trades_adaptive = simulate_strategy_on_real_data(
        df,
        score_entry_min=0.7,
        stop_loss=-0.15,
        risk_scalar_by_regime={'bull': 1.0, 'bear': 0.5, 'sideways': 0.8}
    )
    
    sharpe_adaptive = (trades_adaptive['trade_return'].mean() / trades_adaptive['trade_return'].std() * np.sqrt(252)) if trades_adaptive['trade_return'].std() > 0 else 0
    total_return_adaptive = trades_adaptive['trade_return'].sum()
    win_rate_adaptive = len(trades_adaptive[trades_adaptive['trade_return'] > 0]) / len(trades_adaptive)
    avg_holding_adaptive = trades_adaptive['holding_days'].mean()
    
    print(f"   Trade totali:       {len(trades_adaptive)}")
    print(f"   Return totale:      {total_return_adaptive*100:+.2f}%")
    print(f"   Return medio:       {trades_adaptive['trade_return'].mean()*100:+.2f}%")
    print(f"   Win rate:           {win_rate_adaptive*100:.1f}%")
    print(f"   Sharpe:             {sharpe_adaptive:.3f}")
    print(f"   Holding medio:      {avg_holding_adaptive:.0f} giorni")
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
    
    print(f"   Return Fixed:       {total_return_fixed*100:+.2f}%")
    print(f"   Return Adaptive:    {total_return_adaptive*100:+.2f}%")
    print(f"   Δ Return:           {improvement_return*100:+.2f}%")
    print()
    print(f"   Sharpe Fixed:       {sharpe_fixed:.3f}")
    print(f"   Sharpe Adaptive:    {sharpe_adaptive:.3f}")
    print(f"   Δ Sharpe:           {improvement_sharpe:+.3f}")
    print()
    
    # Analisi drawdown
    print("   📉 Drawdown Analysis:")
    max_dd_fixed = trades_fixed['trade_return'].min()
    max_dd_adaptive = trades_adaptive['trade_return'].min()
    print(f"   Worst trade Fixed:     {max_dd_fixed*100:.2f}%")
    print(f"   Worst trade Adaptive:  {max_dd_adaptive*100:.2f}%")
    print(f"   Δ Worst trade:         {(max_dd_adaptive - max_dd_fixed)*100:+.2f}%")
    print()
    
    if improvement_sharpe > 0.2:
        print("   ✅ ADAPTIVE VINCE: Miglioramento significativo (>0.2 Sharpe)")
        print("   → Vale la pena implementare regime-adaptive system")
        print()
        print("   💡 INSIGHT: Su dati reali, ridurre esposizione in bear/high-vol")
        print("      protegge il capitale e migliora risk-adjusted returns.")
        recommendation = "IMPLEMENT_ADAPTIVE"
    elif improvement_sharpe > 0:
        print("   ⚠️  ADAPTIVE MARGINALE: Miglioramento modesto (<0.2 Sharpe)")
        print("   → Valutare se complessità vale il guadagno")
        print()
        print("   💡 INSIGHT: Adaptive aiuta ma il guadagno è limitato.")
        recommendation = "EVALUATE"
    else:
        print("   ❌ FIXED VINCE: Parametri fissi sufficienti")
        print("   → Non serve complessità aggiuntiva")
        print()
        print("   💡 INSIGHT: In questo periodo storico, parametri fissi sono robusti.")
        recommendation = "KEEP_FIXED"
    
    print()
    
    # Salva risultati
    output_dir = Path(pm.db_path).parent.parent / 'data' / 'reports'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Salva trade
    trades_fixed['strategy'] = 'FIXED'
    trades_adaptive['strategy'] = 'ADAPTIVE'
    all_trades = pd.concat([trades_fixed, trades_adaptive])
    
    trades_path = output_dir / f'poc_real_trades_{symbol}_{timestamp}.csv'
    all_trades.to_csv(trades_path, index=False)
    print(f"💾 Trade salvati: {trades_path}")
    
    # Salva regime history
    regime_path = output_dir / f'poc_real_regime_{symbol}_{timestamp}.csv'
    df.to_csv(regime_path, index=False)
    print(f"💾 Regime history salvato: {regime_path}")
    
    conn.close()
    
    return {
        'recommendation': recommendation,
        'sharpe_fixed': sharpe_fixed,
        'sharpe_adaptive': sharpe_adaptive,
        'improvement_sharpe': improvement_sharpe,
        'improvement_return': improvement_return,
        'symbol': symbol,
        'period': f"{start_date} → {end_date}"
    }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='POC Regime-Adaptive con dati reali')
    parser.add_argument('--symbol', default='VWCE.MI', help='Simbolo ETF')
    parser.add_argument('--start', default='2020-01-01', help='Data inizio')
    parser.add_argument('--end', default='2025-01-01', help='Data fine')
    
    args = parser.parse_args()
    
    results = run_poc_real_data(symbol=args.symbol, start_date=args.start, end_date=args.end)
    
    if results:
        print("\n✅ POC completato con successo")
        print(f"\n🎯 Raccomandazione finale: {results['recommendation']}")
        
        if results['recommendation'] == 'IMPLEMENT_ADAPTIVE':
            print("\n📋 NEXT STEPS:")
            print("   1. Implementare regime_classifier.py")
            print("   2. Estendere backtest_engine con parameter_optimizer.py")
            print("   3. Modificare strategy_engine per usare parametri adattivi")
            print("   4. Test su altri simboli per validazione")
    else:
        print("\n❌ POC fallito - Dati insufficienti")
        sys.exit(1)
