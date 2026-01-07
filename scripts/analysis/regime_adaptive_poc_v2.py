#!/usr/bin/env python3
"""
POC v2: Regime-Adaptive vs Fixed Parameters
Versione semplificata che usa backtest reali esistenti
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_manager import get_path_manager


def classify_regime_from_volatility(volatility: float) -> str:
    """
    Classifica regime basato SOLO su volatility (più semplice e robusto)
    
    Args:
        volatility: Volatilità annualizzata (0.15 = 15%)
    
    Returns:
        "low_vol", "medium_vol", "high_vol"
    """
    if volatility < 0.15:
        return "low_vol"
    elif volatility < 0.25:
        return "medium_vol"
    else:
        return "high_vol"


def analyze_existing_backtest_by_regime(db_path: str, run_id: str = None):
    """
    Analizza backtest esistente raggruppando per regime di volatilità
    """
    
    conn = duckdb.connect(db_path, read_only=True)
    
    print("\n" + "=" * 80)
    print("POC v2: REGIME-ADAPTIVE vs FIXED PARAMETERS")
    print("Analisi su backtest esistente")
    print("=" * 80 + "\n")
    
    # Query trade completati dal ledger
    query = """
    WITH buy_trades AS (
        SELECT 
            symbol,
            date as entry_date,
            qty,
            price as entry_price,
            entry_score,
            run_id,
            id as buy_id
        FROM fiscal_ledger
        WHERE type = 'BUY'
        AND run_type = 'BACKTEST'
    ),
    sell_trades AS (
        SELECT 
            symbol,
            date as exit_date,
            qty,
            price as exit_price,
            exit_reason,
            run_id,
            id as sell_id
        FROM fiscal_ledger
        WHERE type = 'SELL'
        AND run_type = 'BACKTEST'
    ),
    matched_trades AS (
        SELECT 
            b.symbol,
            b.entry_date,
            s.exit_date,
            b.qty,
            b.entry_price,
            s.exit_price,
            b.entry_score,
            s.exit_reason,
            b.run_id,
            (s.exit_price - b.entry_price) / b.entry_price as trade_return,
            b.qty * b.entry_price as capital_invested
        FROM buy_trades b
        JOIN sell_trades s ON b.symbol = s.symbol 
            AND s.exit_date > b.entry_date
            AND b.run_id = s.run_id
        WHERE b.qty = s.qty
    )
    SELECT * FROM matched_trades
    ORDER BY entry_date
    """
    
    trades_df = conn.execute(query).fetchdf()
    
    if len(trades_df) == 0:
        print("❌ Nessun trade trovato nel ledger")
        print("   Esegui prima un backtest con: py scripts/backtest/backtest_runner.py")
        conn.close()
        return None
    
    print(f"📊 Trovati {len(trades_df)} trade completati\n")
    
    # Aggiungi volatility per ogni trade (calcolata al momento entry)
    print("📈 Calcolo volatility per ogni trade...")
    
    for idx, trade in trades_df.iterrows():
        vol_query = """
        SELECT 
            STDDEV(adj_close) OVER (
                ORDER BY date 
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) / AVG(adj_close) OVER (
                ORDER BY date 
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) * SQRT(252) as volatility
        FROM market_data
        WHERE symbol = ?
        AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """
        
        vol_result = conn.execute(vol_query, [trade['symbol'], trade['entry_date']]).fetchone()
        volatility = vol_result[0] if vol_result and vol_result[0] else 0.15
        
        trades_df.at[idx, 'entry_volatility'] = volatility
        trades_df.at[idx, 'regime'] = classify_regime_from_volatility(volatility)
    
    print(f"✅ Volatility calcolata per {len(trades_df)} trade\n")
    
    # Analisi per regime
    print("=" * 80)
    print("ANALISI PER REGIME DI VOLATILITÀ")
    print("=" * 80 + "\n")
    
    regime_stats = {}
    
    for regime in ['low_vol', 'medium_vol', 'high_vol']:
        regime_trades = trades_df[trades_df['regime'] == regime]
        
        if len(regime_trades) == 0:
            print(f"⚠️  {regime:12s}: Nessun trade")
            continue
        
        # Calcola metriche
        total_return = regime_trades['trade_return'].sum()
        avg_return = regime_trades['trade_return'].mean()
        win_rate = len(regime_trades[regime_trades['trade_return'] > 0]) / len(regime_trades)
        sharpe = (regime_trades['trade_return'].mean() / regime_trades['trade_return'].std() * np.sqrt(252)) if regime_trades['trade_return'].std() > 0 else 0
        
        regime_stats[regime] = {
            'n_trades': len(regime_trades),
            'total_return': total_return,
            'avg_return': avg_return,
            'win_rate': win_rate,
            'sharpe': sharpe,
            'avg_volatility': regime_trades['entry_volatility'].mean()
        }
        
        print(f"📌 {regime.upper().replace('_', ' ')}:")
        print(f"   Trade:           {len(regime_trades)}")
        print(f"   Volatility media: {regime_trades['entry_volatility'].mean()*100:.1f}%")
        print(f"   Return totale:   {total_return*100:+.2f}%")
        print(f"   Return medio:    {avg_return*100:+.2f}%")
        print(f"   Win rate:        {win_rate*100:.1f}%")
        print(f"   Sharpe:          {sharpe:.2f}")
        print()
    
    # Confronto strategia adaptive vs fixed
    print("=" * 80)
    print("CONFRONTO: ADAPTIVE vs FIXED")
    print("=" * 80 + "\n")
    
    # Strategia FIXED: stessi parametri per tutti i regimi
    print("📊 STRATEGIA FIXED (parametri uguali per tutti i regimi):")
    total_trades = len(trades_df)
    total_return_fixed = trades_df['trade_return'].sum()
    avg_return_fixed = trades_df['trade_return'].mean()
    sharpe_fixed = (trades_df['trade_return'].mean() / trades_df['trade_return'].std() * np.sqrt(252)) if trades_df['trade_return'].std() > 0 else 0
    
    print(f"   Trade totali:    {total_trades}")
    print(f"   Return totale:   {total_return_fixed*100:+.2f}%")
    print(f"   Return medio:    {avg_return_fixed*100:+.2f}%")
    print(f"   Sharpe:          {sharpe_fixed:.3f}")
    print()
    
    # Strategia ADAPTIVE: parametri diversi per regime
    print("📊 STRATEGIA ADAPTIVE (parametri ottimizzati per regime):")
    print("   Ipotesi: In high_vol riduciamo esposizione del 50%")
    print()
    
    # Simula adaptive: riduci capitale investito in high_vol
    trades_adaptive = trades_df.copy()
    trades_adaptive.loc[trades_adaptive['regime'] == 'high_vol', 'trade_return'] *= 0.5
    
    total_return_adaptive = trades_adaptive['trade_return'].sum()
    avg_return_adaptive = trades_adaptive['trade_return'].mean()
    sharpe_adaptive = (trades_adaptive['trade_return'].mean() / trades_adaptive['trade_return'].std() * np.sqrt(252)) if trades_adaptive['trade_return'].std() > 0 else 0
    
    print(f"   Trade totali:    {total_trades}")
    print(f"   Return totale:   {total_return_adaptive*100:+.2f}%")
    print(f"   Return medio:    {avg_return_adaptive*100:+.2f}%")
    print(f"   Sharpe:          {sharpe_adaptive:.3f}")
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
    
    if improvement_sharpe > 0.2:
        print("   ✅ ADAPTIVE VINCE: Miglioramento significativo (>0.2 Sharpe)")
        print("   → Vale la pena implementare regime-adaptive system")
        recommendation = "IMPLEMENT_ADAPTIVE"
    elif improvement_sharpe > 0:
        print("   ⚠️  ADAPTIVE MARGINALE: Miglioramento modesto (<0.2 Sharpe)")
        print("   → Valutare se complessità vale il guadagno")
        recommendation = "EVALUATE"
    else:
        print("   ❌ FIXED VINCE: Parametri fissi sufficienti")
        print("   → Non serve complessità aggiuntiva")
        recommendation = "KEEP_FIXED"
    
    print()
    
    # Salva report
    pm = get_path_manager()
    output_dir = Path(pm.get_path('reports'))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Salva trade con regime
    trades_path = output_dir / f'regime_analysis_{timestamp}.csv'
    trades_df.to_csv(trades_path, index=False)
    print(f"💾 Trade analysis salvato: {trades_path}")
    
    # Salva regime stats
    stats_df = pd.DataFrame(regime_stats).T
    stats_path = output_dir / f'regime_stats_{timestamp}.csv'
    stats_df.to_csv(stats_path)
    print(f"💾 Regime stats salvati: {stats_path}")
    
    conn.close()
    
    return {
        'recommendation': recommendation,
        'sharpe_fixed': sharpe_fixed,
        'sharpe_adaptive': sharpe_adaptive,
        'improvement_sharpe': improvement_sharpe,
        'regime_stats': regime_stats
    }


if __name__ == '__main__':
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    results = analyze_existing_backtest_by_regime(db_path)
    
    if results:
        print("\n✅ POC v2 completato")
        print(f"\n🎯 Raccomandazione: {results['recommendation']}")
    else:
        print("\n❌ POC v2 fallito - Esegui prima un backtest")
        sys.exit(1)
