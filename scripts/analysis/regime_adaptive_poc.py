#!/usr/bin/env python3
"""
POC: Regime-Adaptive vs Fixed Parameters
Testa se parametri adattivi per regime battono parametri fissi
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import duckdb
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_manager import get_path_manager

def classify_regime_simple(volatility: float, trend: float, volume_ratio: float) -> str:
    """
    Classifica regime basato su metriche osservabili
    
    Args:
        volatility: Volatilità annualizzata (es. 0.15 = 15%)
        trend: Return ultimi N giorni (es. 0.05 = +5%)
        volume_ratio: Volume corrente / media (es. 1.2 = +20% sopra media)
    
    Returns:
        "bull", "bear", "sideways"
    """
    # Regole euristiche più realistiche
    if trend > 0.05 and volatility < 0.20:
        return "bull"
    elif trend < -0.05 and volatility > 0.25:
        return "bear"
    else:
        return "sideways"


def get_market_regime_history(conn, symbol: str, start_date: str, end_date: str, 
                               lookback_days: int = 50) -> pd.DataFrame:
    """
    Calcola regime storico per ogni giorno
    
    Returns:
        DataFrame con colonne: date, volatility, trend, volume_ratio, regime
    """
    
    query = """
    WITH daily_metrics AS (
        SELECT 
            date,
            symbol,
            adj_close,
            volume,
            -- Volatility ultimi N giorni
            STDDEV(adj_close) OVER (
                PARTITION BY symbol 
                ORDER BY date 
                ROWS BETWEEN ? PRECEDING AND CURRENT ROW
            ) / AVG(adj_close) OVER (
                PARTITION BY symbol 
                ORDER BY date 
                ROWS BETWEEN ? PRECEDING AND CURRENT ROW
            ) * SQRT(252) as volatility,
            -- Trend ultimi N giorni
            (adj_close - LAG(adj_close, ?) OVER (PARTITION BY symbol ORDER BY date)) 
            / LAG(adj_close, ?) OVER (PARTITION BY symbol ORDER BY date) as trend,
            -- Volume ratio
            volume / AVG(volume) OVER (
                PARTITION BY symbol 
                ORDER BY date 
                ROWS BETWEEN ? PRECEDING AND CURRENT ROW
            ) as volume_ratio
        FROM market_data
        WHERE symbol = ?
        AND date BETWEEN ? AND ?
    )
    SELECT 
        date,
        COALESCE(volatility, 0.15) as volatility,
        COALESCE(trend, 0.0) as trend,
        COALESCE(volume_ratio, 1.0) as volume_ratio
    FROM daily_metrics
    WHERE date >= ?
    ORDER BY date
    """
    
    df = conn.execute(query, [
        lookback_days, lookback_days,  # volatility
        lookback_days, lookback_days,  # trend
        lookback_days,  # volume_ratio
        symbol, start_date, end_date,
        start_date  # Filter dopo calcolo metriche
    ]).fetchdf()
    
    # Classifica regime
    df['regime'] = df.apply(
        lambda row: classify_regime_simple(row['volatility'], row['trend'], row['volume_ratio']),
        axis=1
    )
    
    return df


def calibrate_params_for_regime(conn, symbol: str, regime: str, 
                                 regime_dates: List[str]) -> Dict:
    """
    Calibra parametri ottimali per un regime specifico tramite grid search
    
    Args:
        symbol: Simbolo ETF
        regime: "bull", "bear", "sideways"
        regime_dates: Lista date in cui il simbolo era in quel regime
    
    Returns:
        Dict con parametri ottimali e metriche (None se calibrazione fallisce)
    """
    
    # Grid search parametri
    score_entry_candidates = [0.5, 0.6, 0.7, 0.8]
    stop_loss_candidates = [-0.10, -0.15, -0.20]
    
    best_sharpe = -999
    best_params = None
    
    print(f"  Calibrando {regime} regime ({len(regime_dates)} giorni)...")
    
    for score_entry in score_entry_candidates:
        for stop_loss in stop_loss_candidates:
            # Simula strategia con questi parametri
            sharpe = simulate_strategy(
                conn, symbol, regime_dates, 
                score_entry_min=score_entry,
                stop_loss=stop_loss
            )
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = {
                    'score_entry_min': score_entry,
                    'stop_loss': stop_loss,
                    'sharpe': sharpe
                }
    
    # Fallback se nessun parametro valido
    if best_params is None:
        best_params = {
            'score_entry_min': 0.7,
            'stop_loss': -0.15,
            'sharpe': -999
        }
    
    return best_params


def simulate_strategy(conn, symbol: str, dates: List[str], 
                      score_entry_min: float, stop_loss: float) -> float:
    """
    Simula strategia semplificata e calcola Sharpe
    
    Returns:
        Sharpe ratio
    """
    
    # Converti date a string se necessario
    dates_clean = [str(d)[:10] if not isinstance(d, str) else d[:10] for d in dates]
    
    if len(dates_clean) < 20:
        return -999
    
    # Usa range date invece di IN per performance
    min_date = min(dates_clean)
    max_date = max(dates_clean)
    
    query = """
    WITH signals AS (
        SELECT 
            date,
            adj_close,
            LAG(adj_close, 1) OVER (ORDER BY date) as prev_close,
            -- Momentum score semplificato
            (adj_close - LAG(adj_close, 20) OVER (ORDER BY date)) 
            / LAG(adj_close, 20) OVER (ORDER BY date) as momentum_score
        FROM market_data
        WHERE symbol = ?
        AND date BETWEEN ? AND ?
    )
    SELECT 
        date,
        adj_close,
        prev_close,
        COALESCE(momentum_score, 0.0) as momentum_score
    FROM signals
    WHERE prev_close IS NOT NULL
    ORDER BY date
    """
    
    try:
        df = conn.execute(query, [symbol, min_date, max_date]).fetchdf()
    except Exception as e:
        print(f"      ⚠️  Query error: {e}")
        return -999  # Dati insufficienti
    
    if len(df) < 20:
        return -999
    
    # Simula trade
    returns = []
    position = 0
    entry_price = 0
    
    for idx, row in df.iterrows():
        # Entry signal
        if position == 0 and row['momentum_score'] >= score_entry_min:
            position = 1
            entry_price = row['adj_close']
        
        # Exit signal (stop-loss)
        elif position == 1:
            current_return = (row['adj_close'] - entry_price) / entry_price
            if current_return <= stop_loss:
                returns.append(current_return)
                position = 0
            # Hold position
    
    # Close final position
    if position == 1 and len(df) > 0:
        final_return = (df.iloc[-1]['adj_close'] - entry_price) / entry_price
        returns.append(final_return)
    
    if len(returns) == 0:
        return -999
    
    # Calcola Sharpe
    returns_arr = np.array(returns)
    if returns_arr.std() == 0:
        return 0
    
    sharpe = returns_arr.mean() / returns_arr.std() * np.sqrt(252)
    return sharpe


def run_poc(symbol: str = 'VWCE.MI', start_date: str = '2018-01-01', 
            end_date: str = '2025-01-01'):
    """
    Esegue POC completo: classifica regimi, calibra parametri, confronta performance
    """
    
    pm = get_path_manager()
    db_path = str(pm.db_path)
    conn = duckdb.connect(db_path, read_only=True)
    
    print("\n" + "=" * 80)
    print("POC: REGIME-ADAPTIVE vs FIXED PARAMETERS")
    print("=" * 80 + "\n")
    print(f"Simbolo: {symbol}")
    print(f"Periodo: {start_date} → {end_date}\n")
    
    # Step 1: Classifica regime storico
    print("📊 Step 1: Classificazione regime storico...")
    regime_history = get_market_regime_history(conn, symbol, start_date, end_date)
    
    if len(regime_history) == 0:
        print(f"❌ Nessun dato trovato per {symbol}")
        conn.close()
        return
    
    print(f"   Trovati {len(regime_history)} giorni di dati\n")
    
    # Distribuzione regimi
    regime_counts = regime_history['regime'].value_counts()
    print("   Distribuzione regimi:")
    for regime, count in regime_counts.items():
        pct = count / len(regime_history) * 100
        print(f"   - {regime:10s}: {count:4d} giorni ({pct:5.1f}%)")
    print()
    
    # Metriche medie per regime
    print("   Metriche medie per regime:")
    for regime in ['bull', 'bear', 'sideways']:
        regime_data = regime_history[regime_history['regime'] == regime]
        if len(regime_data) > 0:
            print(f"   - {regime:10s}: vol={regime_data['volatility'].mean()*100:5.1f}%, "
                  f"trend={regime_data['trend'].mean()*100:+6.2f}%")
    print()
    
    # Step 2: Calibra parametri per regime
    print("🔧 Step 2: Calibrazione parametri per regime...")
    
    params_by_regime = {}
    for regime in ['bull', 'bear', 'sideways']:
        regime_dates = regime_history[regime_history['regime'] == regime]['date'].tolist()
        if len(regime_dates) < 50:
            print(f"   ⚠️  {regime}: Dati insufficienti (< 50 giorni), skip")
            continue
        
        params = calibrate_params_for_regime(conn, symbol, regime, regime_dates)
        params_by_regime[regime] = params
        
        print(f"   ✅ {regime:10s}: score_entry={params['score_entry_min']:.1f}, "
              f"stop_loss={params['stop_loss']:.2f}, sharpe={params['sharpe']:.2f}")
    
    print()
    
    # Step 3: Confronta performance adaptive vs fixed
    print("📈 Step 3: Confronto performance...")
    print()
    
    # Fixed params (baseline)
    fixed_params = {'score_entry_min': 0.7, 'stop_loss': -0.15}
    print(f"   Parametri FISSI: score_entry={fixed_params['score_entry_min']:.1f}, "
          f"stop_loss={fixed_params['stop_loss']:.2f}")
    
    all_dates = regime_history['date'].tolist()
    sharpe_fixed = simulate_strategy(
        conn, symbol, all_dates,
        score_entry_min=fixed_params['score_entry_min'],
        stop_loss=fixed_params['stop_loss']
    )
    print(f"   Sharpe FISSI:    {sharpe_fixed:.3f}")
    print()
    
    # Adaptive params
    print("   Parametri ADATTIVI per regime:")
    sharpe_adaptive_total = 0
    total_days = 0
    
    for regime in ['bull', 'bear', 'sideways']:
        if regime not in params_by_regime:
            continue
        
        regime_dates = regime_history[regime_history['regime'] == regime]['date'].tolist()
        params = params_by_regime[regime]
        
        sharpe_regime = simulate_strategy(
            conn, symbol, regime_dates,
            score_entry_min=params['score_entry_min'],
            stop_loss=params['stop_loss']
        )
        
        # Weighted average
        weight = len(regime_dates) / len(regime_history)
        sharpe_adaptive_total += sharpe_regime * weight
        total_days += len(regime_dates)
        
        print(f"   - {regime:10s}: sharpe={sharpe_regime:.3f} "
              f"(score={params['score_entry_min']:.1f}, stop={params['stop_loss']:.2f})")
    
    print()
    print(f"   Sharpe ADAPTIVE: {sharpe_adaptive_total:.3f} (weighted avg)")
    print()
    
    # Verdict
    print("=" * 80)
    print("VERDICT")
    print("=" * 80 + "\n")
    
    improvement = sharpe_adaptive_total - sharpe_fixed
    improvement_pct = (improvement / abs(sharpe_fixed)) * 100 if sharpe_fixed != 0 else 0
    
    print(f"   Sharpe Fixed:    {sharpe_fixed:.3f}")
    print(f"   Sharpe Adaptive: {sharpe_adaptive_total:.3f}")
    print(f"   Miglioramento:   {improvement:+.3f} ({improvement_pct:+.1f}%)")
    print()
    
    if improvement > 0.2:
        print("   ✅ ADAPTIVE VINCE: Miglioramento significativo (>0.2 Sharpe)")
        print("   → Vale la pena implementare regime-adaptive system")
    elif improvement > 0:
        print("   ⚠️  ADAPTIVE MARGINALE: Miglioramento modesto (<0.2 Sharpe)")
        print("   → Valutare se complessità vale il guadagno")
    else:
        print("   ❌ FIXED VINCE: Parametri fissi sufficienti")
        print("   → Non serve complessità aggiuntiva")
    
    print()
    
    # Salva risultati
    output_dir = Path(pm.get_path('reports'))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Salva regime history
    regime_path = output_dir / f'regime_history_{symbol}_{timestamp}.csv'
    regime_history.to_csv(regime_path, index=False)
    print(f"💾 Regime history salvato: {regime_path}")
    
    # Salva parametri calibrati
    params_df = pd.DataFrame([
        {'regime': regime, **params} 
        for regime, params in params_by_regime.items()
    ])
    params_path = output_dir / f'calibrated_params_{symbol}_{timestamp}.csv'
    params_df.to_csv(params_path, index=False)
    print(f"💾 Parametri calibrati salvati: {params_path}")
    
    conn.close()
    
    return {
        'sharpe_fixed': sharpe_fixed,
        'sharpe_adaptive': sharpe_adaptive_total,
        'improvement': improvement,
        'params_by_regime': params_by_regime
    }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='POC Regime-Adaptive vs Fixed')
    parser.add_argument('--symbol', default='VWCE.MI', help='Simbolo ETF')
    parser.add_argument('--start', default='2018-01-01', help='Data inizio')
    parser.add_argument('--end', default='2025-01-01', help='Data fine')
    
    args = parser.parse_args()
    
    results = run_poc(symbol=args.symbol, start_date=args.start, end_date=args.end)
    
    if results:
        print("\n✅ POC completato")
    else:
        print("\n❌ POC fallito")
        sys.exit(1)
