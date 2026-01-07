#!/usr/bin/env python3
"""
Diagnostica Execution Rate & Sizing - ETF Italia Project v10
Analizza perché l'execution rate è basso nonostante molti segnali RISK_ON
"""

import sys
import os
from pathlib import Path
import duckdb
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.path_manager import get_path_manager

def analyze_execution_rate(start_date='2025-01-05', end_date='2026-01-05'):
    """Analizza execution rate e sizing per identificare bottleneck"""
    
    pm = get_path_manager()
    db_path = pm.db_path
    
    conn = duckdb.connect(str(db_path), read_only=True)
    
    print("=" * 80)
    print("DIAGNOSTICA EXECUTION RATE & SIZING")
    print("=" * 80)
    print(f"Periodo: {start_date} → {end_date}\n")
    
    results = {}
    
    # 1. Conteggi base
    print("📊 1. CONTEGGI BASE")
    print("-" * 80)
    
    trading_days = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM signals WHERE date BETWEEN ? AND ?",
        [start_date, end_date]
    ).fetchone()[0]
    
    signals_by_state = conn.execute(
        """
        SELECT signal_state, COUNT(*) as n
        FROM signals
        WHERE date BETWEEN ? AND ?
        GROUP BY signal_state
        ORDER BY n DESC
        """,
        [start_date, end_date]
    ).fetchall()
    
    orders_executed = conn.execute(
        """
        SELECT COUNT(*)
        FROM fiscal_ledger
        WHERE run_type = 'BACKTEST'
          AND type IN ('BUY', 'SELL')
          AND date BETWEEN ? AND ?
        """,
        [start_date, end_date]
    ).fetchone()[0]
    
    print(f"Trading days: {trading_days}")
    print(f"Signals by state:")
    for state, n in signals_by_state:
        print(f"  - {state}: {n}")
    print(f"Orders executed: {orders_executed}")
    print(f"Execution rate: {orders_executed / trading_days:.2%}\n")
    
    results['base_counts'] = {
        'trading_days': int(trading_days),
        'signals_by_state': {state: int(n) for state, n in signals_by_state},
        'orders_executed': int(orders_executed),
        'execution_rate': float(orders_executed / trading_days) if trading_days else 0.0
    }
    
    # 2. Distribuzione risk_scalar per RISK_ON
    print("📊 2. DISTRIBUZIONE RISK_SCALAR (RISK_ON)")
    print("-" * 80)
    
    risk_scalar_dist = conn.execute(
        """
        SELECT
            COUNT(*) as n,
            MIN(risk_scalar) as min_val,
            AVG(risk_scalar) as avg_val,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY risk_scalar) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY risk_scalar) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY risk_scalar) as p75,
            MAX(risk_scalar) as max_val
        FROM signals
        WHERE date BETWEEN ? AND ?
          AND signal_state = 'RISK_ON'
        """,
        [start_date, end_date]
    ).fetchone()
    
    print(f"RISK_ON signals: {risk_scalar_dist[0]}")
    print(f"Risk scalar stats:")
    print(f"  - Min: {risk_scalar_dist[1]:.3f}")
    print(f"  - P25: {risk_scalar_dist[3]:.3f}")
    print(f"  - Median: {risk_scalar_dist[4]:.3f}")
    print(f"  - P75: {risk_scalar_dist[5]:.3f}")
    print(f"  - Max: {risk_scalar_dist[6]:.3f}")
    print(f"  - Avg: {risk_scalar_dist[2]:.3f}\n")
    
    results['risk_scalar_dist'] = {
        'n': int(risk_scalar_dist[0]),
        'min': float(risk_scalar_dist[1]),
        'p25': float(risk_scalar_dist[3]),
        'median': float(risk_scalar_dist[4]),
        'p75': float(risk_scalar_dist[5]),
        'max': float(risk_scalar_dist[6]),
        'avg': float(risk_scalar_dist[2])
    }
    
    # 3. Distribuzione risk_scalar < 0.3 (molto bassi)
    low_risk_scalar = conn.execute(
        """
        SELECT COUNT(*)
        FROM signals
        WHERE date BETWEEN ? AND ?
          AND signal_state = 'RISK_ON'
          AND risk_scalar < 0.3
        """,
        [start_date, end_date]
    ).fetchone()[0]
    
    print(f"RISK_ON con risk_scalar < 0.3: {low_risk_scalar} ({low_risk_scalar / risk_scalar_dist[0]:.1%})\n")
    
    results['low_risk_scalar_count'] = int(low_risk_scalar)
    results['low_risk_scalar_pct'] = float(low_risk_scalar / risk_scalar_dist[0]) if risk_scalar_dist[0] else 0.0
    
    # 4. Analisi prezzi ETF (per capire qty rounding)
    print("📊 3. PREZZI ETF (per qty rounding)")
    print("-" * 80)
    
    price_stats = conn.execute(
        """
        SELECT
            s.symbol,
            COUNT(*) as n_signals,
            MIN(md.close) as min_price,
            AVG(md.close) as avg_price,
            MAX(md.close) as max_price
        FROM signals s
        JOIN market_data md ON s.symbol = md.symbol AND s.date = md.date
        WHERE s.date BETWEEN ? AND ?
          AND s.signal_state = 'RISK_ON'
        GROUP BY s.symbol
        ORDER BY avg_price DESC
        """,
        [start_date, end_date]
    ).fetchall()
    
    print("Symbol | N signals | Min price | Avg price | Max price")
    print("-" * 80)
    for symbol, n, min_p, avg_p, max_p in price_stats:
        print(f"{symbol:10} | {n:9} | €{min_p:8.2f} | €{avg_p:8.2f} | €{max_p:8.2f}")
    print()
    
    results['price_stats'] = [
        {
            'symbol': symbol,
            'n_signals': int(n),
            'min_price': float(min_p),
            'avg_price': float(avg_p),
            'max_price': float(max_p)
        }
        for symbol, n, min_p, avg_p, max_p in price_stats
    ]
    
    # 5. Simulazione qty con risk_scalar tipici
    print("📊 4. SIMULAZIONE QTY (con portfolio €20k)")
    print("-" * 80)
    
    portfolio_value = 20000
    print(f"Portfolio value: €{portfolio_value:,.2f}")
    print(f"Assumendo target_weight = 0.33 (1/3 portfolio per symbol)\n")
    
    for symbol, n, min_p, avg_p, max_p in price_stats:
        print(f"{symbol}:")
        for risk_scalar_val in [0.15, 0.30, 0.50, 0.70, 1.00]:
            target_value = portfolio_value * 0.33 * risk_scalar_val
            qty_at_avg = int(target_value / avg_p)
            print(f"  risk_scalar={risk_scalar_val:.2f} → target_value=€{target_value:6.0f} → qty={qty_at_avg:3} (price €{avg_p:.2f})")
        print()
    
    # 6. Cash disponibile nel periodo
    print("📊 5. CASH DISPONIBILE (BACKTEST)")
    print("-" * 80)
    
    cash_stats = conn.execute(
        """
        WITH cash_by_date AS (
            SELECT
                date,
                SUM(CASE WHEN type = 'INIT' THEN qty * price
                         WHEN type = 'BUY' THEN -(qty * price)
                         WHEN type = 'SELL' THEN qty * price
                         ELSE 0 END) as cash_change
            FROM fiscal_ledger
            WHERE run_type = 'BACKTEST'
              AND date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        ),
        cash_cumulative AS (
            SELECT
                date,
                SUM(cash_change) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cash_balance
            FROM cash_by_date
        )
        SELECT
            MIN(cash_balance) as min_cash,
            AVG(cash_balance) as avg_cash,
            MAX(cash_balance) as max_cash
        FROM cash_cumulative
        """,
        [start_date, end_date]
    ).fetchone()
    
    if cash_stats and cash_stats[0] is not None:
        print(f"Cash balance stats:")
        print(f"  - Min: €{cash_stats[0]:,.2f}")
        print(f"  - Avg: €{cash_stats[1]:,.2f}")
        print(f"  - Max: €{cash_stats[2]:,.2f}\n")
        
        results['cash_stats'] = {
            'min': float(cash_stats[0]),
            'avg': float(cash_stats[1]),
            'max': float(cash_stats[2])
        }
    else:
        print("  (Nessun dato cash disponibile)\n")
        results['cash_stats'] = None
    
    # 7. Ordini effettivamente eseguiti
    print("📊 6. ORDINI ESEGUITI (dettaglio)")
    print("-" * 80)
    
    orders_detail = conn.execute(
        """
        SELECT
            date,
            symbol,
            type,
            qty,
            price,
            (qty * price) as amount
        FROM fiscal_ledger
        WHERE run_type = 'BACKTEST'
          AND type IN ('BUY', 'SELL')
          AND date BETWEEN ? AND ?
        ORDER BY date, symbol
        """,
        [start_date, end_date]
    ).fetchall()
    
    print(f"Total orders: {len(orders_detail)}")
    if orders_detail:
        print("\nDate       | Symbol     | Type | Qty | Price    | Amount")
        print("-" * 80)
        for date, symbol, typ, qty, price, amount in orders_detail[:20]:  # Prime 20
            print(f"{date} | {symbol:10} | {typ:4} | {qty:3} | €{price:7.2f} | €{amount:9.2f}")
        if len(orders_detail) > 20:
            print(f"... ({len(orders_detail) - 20} ordini aggiuntivi)")
    print()
    
    results['orders_detail'] = [
        {
            'date': str(date),
            'symbol': symbol,
            'type': typ,
            'qty': int(qty),
            'price': float(price),
            'amount': float(amount)
        }
        for date, symbol, typ, qty, price, amount in orders_detail
    ]
    
    conn.close()
    
    # 8. Conclusioni diagnostiche
    print("=" * 80)
    print("📋 CONCLUSIONI DIAGNOSTICHE")
    print("=" * 80)
    
    conclusions = []
    
    # Check 1: Risk scalar basso
    if results['risk_scalar_dist']['median'] < 0.5:
        conclusions.append({
            'issue': 'RISK_SCALAR_BASSO',
            'severity': 'HIGH',
            'description': f"Mediana risk_scalar = {results['risk_scalar_dist']['median']:.3f} < 0.5",
            'impact': 'Target value ridotto → qty spesso = 0 dopo int() rounding'
        })
        print("⚠️  RISK_SCALAR_BASSO: Mediana < 0.5 → target value troppo basso")
    
    # Check 2: Prezzi alti
    avg_price_all = sum(p['avg_price'] for p in results['price_stats']) / len(results['price_stats']) if results['price_stats'] else 0
    if avg_price_all > 50:
        conclusions.append({
            'issue': 'PREZZI_ALTI',
            'severity': 'MEDIUM',
            'description': f"Prezzo medio ETF = €{avg_price_all:.2f}",
            'impact': 'Con target value basso (es. €1000), qty = int(1000/80) = 12 → accettabile, ma con risk_scalar < 0.3 → qty = 0'
        })
        print(f"⚠️  PREZZI_ALTI: Prezzo medio €{avg_price_all:.2f} → amplifica effetto risk_scalar basso")
    
    # Check 3: Low risk scalar count
    if results['low_risk_scalar_pct'] > 0.3:
        conclusions.append({
            'issue': 'MOLTI_RISK_SCALAR_BASSI',
            'severity': 'HIGH',
            'description': f"{results['low_risk_scalar_pct']:.1%} dei RISK_ON hanno risk_scalar < 0.3",
            'impact': 'Questi segnali finiscono quasi sempre con qty = 0'
        })
        print(f"⚠️  MOLTI_RISK_SCALAR_BASSI: {results['low_risk_scalar_pct']:.1%} con risk_scalar < 0.3")
    
    # Check 4: Cash gating
    if results['cash_stats'] and results['cash_stats']['avg'] < 5000:
        conclusions.append({
            'issue': 'CASH_BASSO',
            'severity': 'MEDIUM',
            'description': f"Cash medio = €{results['cash_stats']['avg']:,.2f}",
            'impact': 'Possibile cash gating su ordini anche piccoli'
        })
        print(f"⚠️  CASH_BASSO: Cash medio €{results['cash_stats']['avg']:,.2f} → possibile gating")
    
    if not conclusions:
        print("✅ Nessun issue critico identificato (execution rate basso ma coerente con parametri)")
    
    print("\n" + "=" * 80)
    
    results['conclusions'] = conclusions
    results['timestamp'] = datetime.now().isoformat()
    
    return results


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Diagnostica execution rate & sizing')
    parser.add_argument('--start-date', default='2025-01-05', help='Data inizio')
    parser.add_argument('--end-date', default='2026-01-05', help='Data fine')
    parser.add_argument('--output', help='File output JSON (opzionale)')
    
    args = parser.parse_args()
    
    results = analyze_execution_rate(args.start_date, args.end_date)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Risultati salvati in: {output_path}")
    
    return results


if __name__ == '__main__':
    main()
