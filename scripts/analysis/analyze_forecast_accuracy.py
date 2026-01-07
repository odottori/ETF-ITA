#!/usr/bin/env python3
"""
Forecast Accuracy Analysis - ETF Italia Project
Analizza accuracy del forecast confrontando metriche previste vs realizzate per ogni trade
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_manager import get_path_manager

def analyze_forecast_accuracy(run_type='BACKTEST', min_trades=1):
    """
    Analizza accuracy forecast per ogni trade completato
    
    Metriche analizzate:
    - Durata prevista vs reale
    - Capitale investito
    - Resa (return) prevista vs reale
    - Rischio (volatilità) stimato vs reale
    - Exit reason (planned vs forced)
    """
    
    pm = get_path_manager()
    db_path = str(pm.db_path)
    conn = duckdb.connect(db_path)
    
    print("\n" + "=" * 80)
    print("FORECAST ACCURACY ANALYSIS - Post-Cast Report")
    print("=" * 80 + "\n")
    
    # Query trade completati (BUY + SELL matched)
    trades_df = conn.execute("""
    WITH buy_trades AS (
        SELECT 
            symbol,
            date as entry_date,
            qty,
            price as entry_price,
            entry_score,
            expected_holding_days,
            expected_exit_date,
            run_id,
            id as buy_id
        FROM fiscal_ledger
        WHERE type = 'BUY'
        AND run_type = ?
        AND entry_score IS NOT NULL
    ),
    sell_trades AS (
        SELECT 
            symbol,
            date as exit_date,
            qty,
            price as exit_price,
            exit_reason,
            actual_holding_days,
            run_id,
            id as sell_id
        FROM fiscal_ledger
        WHERE type = 'SELL'
        AND run_type = ?
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
            b.expected_holding_days,
            b.expected_exit_date,
            s.actual_holding_days,
            s.exit_reason,
            b.run_id,
            -- Calcola metriche
            (s.exit_price - b.entry_price) / b.entry_price as actual_return,
            b.qty * b.entry_price as capital_invested,
            (s.exit_price - b.entry_price) * b.qty as profit_loss
        FROM buy_trades b
        JOIN sell_trades s ON b.symbol = s.symbol 
            AND s.exit_date > b.entry_date
            AND b.run_id = s.run_id
        WHERE b.qty = s.qty  -- Match esatto qty
    )
    SELECT * FROM matched_trades
    ORDER BY entry_date
    """, [run_type, run_type]).fetchdf()
    
    if len(trades_df) == 0:
        print(f"⚠️  Nessun trade completato trovato per run_type={run_type}")
        return None
    
    print(f"📊 Trovati {len(trades_df)} trade completati\n")
    
    # Calcola metriche aggregate
    trades_df['holding_error_days'] = trades_df['actual_holding_days'] - trades_df['expected_holding_days']
    trades_df['holding_error_pct'] = (trades_df['holding_error_days'] / trades_df['expected_holding_days']) * 100
    
    # Calcola volatilità realizzata per ogni trade
    for idx, trade in trades_df.iterrows():
        vol_data = conn.execute("""
        SELECT AVG(
            (high - low) / ((high + low) / 2)
        ) * SQRT(252) as realized_vol
        FROM market_data
        WHERE symbol = ?
        AND date BETWEEN ? AND ?
        """, [trade['symbol'], trade['entry_date'], trade['exit_date']]).fetchone()
        
        trades_df.at[idx, 'realized_volatility'] = vol_data[0] if vol_data[0] else 0.15
    
    # Report per trade
    print("=" * 80)
    print("DETTAGLIO TRADE (Forecast vs Actual)")
    print("=" * 80 + "\n")
    
    for idx, trade in trades_df.iterrows():
        print(f"Trade #{idx+1}: {trade['symbol']}")
        print("-" * 80)
        print(f"  📅 Entry: {trade['entry_date']} | Exit: {trade['exit_date']}")
        print(f"  💰 Capitale: €{trade['capital_invested']:,.2f} | P&L: €{trade['profit_loss']:,.2f}")
        print(f"  📈 Return: {trade['actual_return']*100:.2f}%")
        print(f"  📊 Entry Score: {trade['entry_score']:.3f}")
        print()
        print(f"  ⏱️  DURATA:")
        print(f"     Prevista: {trade['expected_holding_days']:.0f} giorni")
        print(f"     Reale:    {trade['actual_holding_days']:.0f} giorni")
        print(f"     Errore:   {trade['holding_error_days']:.0f} giorni ({trade['holding_error_pct']:.1f}%)")
        print()
        print(f"  🎯 EXIT:")
        print(f"     Data prevista: {trade['expected_exit_date']}")
        print(f"     Data reale:    {trade['exit_date']}")
        print(f"     Motivo:        {trade['exit_reason']}")
        print()
        print(f"  📉 RISCHIO:")
        print(f"     Volatilità realizzata: {trade['realized_volatility']*100:.2f}%")
        print()
    
    # Summary statistiche
    print("=" * 80)
    print("SUMMARY STATISTICHE")
    print("=" * 80 + "\n")
    
    print(f"📊 PERFORMANCE:")
    print(f"   Totale trade:        {len(trades_df)}")
    print(f"   Trade vincenti:      {len(trades_df[trades_df['actual_return'] > 0])} ({len(trades_df[trades_df['actual_return'] > 0])/len(trades_df)*100:.1f}%)")
    print(f"   Trade perdenti:      {len(trades_df[trades_df['actual_return'] < 0])} ({len(trades_df[trades_df['actual_return'] < 0])/len(trades_df)*100:.1f}%)")
    print(f"   Return medio:        {trades_df['actual_return'].mean()*100:.2f}%")
    print(f"   Return mediano:      {trades_df['actual_return'].median()*100:.2f}%")
    print(f"   Miglior trade:       {trades_df['actual_return'].max()*100:.2f}%")
    print(f"   Peggior trade:       {trades_df['actual_return'].min()*100:.2f}%")
    print()
    
    print(f"⏱️  FORECAST ACCURACY (Durata):")
    print(f"   Durata media prevista:  {trades_df['expected_holding_days'].mean():.1f} giorni")
    print(f"   Durata media reale:     {trades_df['actual_holding_days'].mean():.1f} giorni")
    print(f"   Errore medio:           {trades_df['holding_error_days'].mean():.1f} giorni")
    print(f"   Errore medio %:         {trades_df['holding_error_pct'].mean():.1f}%")
    print(f"   MAE (Mean Abs Error):   {trades_df['holding_error_days'].abs().mean():.1f} giorni")
    print()
    
    print(f"🎯 EXIT REASON DISTRIBUTION:")
    exit_reasons = trades_df['exit_reason'].value_counts()
    for reason, count in exit_reasons.items():
        print(f"   {reason}: {count} ({count/len(trades_df)*100:.1f}%)")
    print()
    
    print(f"📉 RISCHIO:")
    print(f"   Volatilità media realizzata: {trades_df['realized_volatility'].mean()*100:.2f}%")
    print(f"   Volatilità max:              {trades_df['realized_volatility'].max()*100:.2f}%")
    print(f"   Volatilità min:              {trades_df['realized_volatility'].min()*100:.2f}%")
    print()
    
    # Analisi per simbolo
    print("=" * 80)
    print("ANALISI PER SIMBOLO")
    print("=" * 80 + "\n")
    
    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol]
        print(f"📌 {symbol}:")
        print(f"   Trade:           {len(symbol_trades)}")
        print(f"   Return medio:    {symbol_trades['actual_return'].mean()*100:.2f}%")
        print(f"   Durata media:    {symbol_trades['actual_holding_days'].mean():.1f} giorni (prevista: {symbol_trades['expected_holding_days'].mean():.1f})")
        print(f"   Win rate:        {len(symbol_trades[symbol_trades['actual_return'] > 0])/len(symbol_trades)*100:.1f}%")
        print()
    
    # Salva report
    output_dir = pm.project_root / 'data' / 'reports'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = output_dir / f'forecast_accuracy_{timestamp}.csv'
    trades_df.to_csv(csv_path, index=False)
    
    print(f"💾 Report salvato: {csv_path}")
    
    conn.close()
    return trades_df


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Analizza accuracy forecast')
    parser.add_argument('--run-type', default='BACKTEST', help='Run type (BACKTEST o PRODUCTION)')
    parser.add_argument('--min-trades', type=int, default=1, help='Minimo trade per analisi')
    
    args = parser.parse_args()
    
    df = analyze_forecast_accuracy(run_type=args.run_type, min_trades=args.min_trades)
    
    if df is not None:
        print("\n✅ Analisi completata")
    else:
        print("\n❌ Analisi fallita")
        sys.exit(1)
