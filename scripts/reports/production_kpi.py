#!/usr/bin/env python3
"""
Production KPI - ETF Italia Project v10.8
Calcola metriche per forecast (dry-run) e postcast (post-execution)
"""

import sys
import os
import json
import duckdb
from datetime import datetime
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager

def calculate_forecast_kpi(orders_file, db_path):
    """
    Calcola KPI per forecast (ordini proposti dry-run)
    
    Metriche:
    - Numero ordini per tipo (BUY/SELL/HOLD)
    - Capitale richiesto totale
    - Esposizione stimata
    - Risk score medio
    - Momentum score medio
    - Costi stimati totali
    """
    
    # Carica ordini
    with open(orders_file, 'r') as f:
        orders_data = json.load(f)
    
    orders = orders_data.get('orders', [])
    
    # Connetti al DB per ottenere portfolio attuale
    conn = duckdb.connect(db_path)
    
    # Portfolio value attuale
    portfolio_value = conn.execute("""
    WITH current_positions AS (
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL') AND run_type = 'PRODUCTION'
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) > 0
    ),
    current_prices AS (
        SELECT md.symbol, md.close as current_price
        FROM market_data md
        WHERE md.date = (SELECT MAX(date) FROM market_data)
    )
    SELECT COALESCE(SUM(cp.qty * cp2.current_price), 0) as market_value
    FROM current_positions cp
    JOIN current_prices cp2 ON cp.symbol = cp2.symbol
    """).fetchone()[0]
    
    # Cash disponibile
    cash_balance = conn.execute("""
    SELECT COALESCE(SUM(CASE 
        WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
        WHEN type = 'SELL' THEN qty * price - fees - tax_paid
        WHEN type = 'BUY' THEN -(qty * price + fees)
        ELSE 0 
    END), 0) as cash_balance
    FROM fiscal_ledger
    WHERE run_type = 'PRODUCTION'
    """).fetchone()[0]
    
    conn.close()
    
    # Calcola metriche forecast
    buy_orders = [o for o in orders if o['action'] == 'BUY']
    sell_orders = [o for o in orders if o['action'] == 'SELL']
    hold_orders = [o for o in orders if o['action'] == 'HOLD']
    
    total_buy_value = sum(o['qty'] * o['price'] for o in buy_orders)
    total_sell_value = sum(o['qty'] * o['price'] for o in sell_orders)
    total_costs = sum(o.get('fees_est', 0) + o.get('tax_friction_est', 0) for o in orders)
    
    avg_momentum = sum(o.get('momentum_score', 0) for o in orders) / len(orders) if orders else 0
    avg_trade_score = sum(o.get('trade_score', 0) for o in orders) / len(orders) if orders else 0
    
    # Esposizione stimata post-execution
    estimated_exposure = portfolio_value + total_buy_value - total_sell_value
    estimated_cash = cash_balance - total_buy_value + total_sell_value - total_costs
    
    kpi = {
        'timestamp': datetime.now().isoformat(),
        'type': 'forecast',
        'orders_file': str(orders_file),
        'portfolio': {
            'current_value': float(portfolio_value),
            'current_cash': float(cash_balance),
            'total_value': float(portfolio_value + cash_balance)
        },
        'orders_summary': {
            'total_orders': len(orders),
            'buy_orders': len(buy_orders),
            'sell_orders': len(sell_orders),
            'hold_orders': len(hold_orders)
        },
        'capital_impact': {
            'total_buy_value': float(total_buy_value),
            'total_sell_value': float(total_sell_value),
            'net_capital_change': float(total_sell_value - total_buy_value),
            'total_costs': float(total_costs)
        },
        'estimated_post_execution': {
            'portfolio_value': float(estimated_exposure),
            'cash_balance': float(estimated_cash),
            'total_value': float(estimated_exposure + estimated_cash),
            'exposure_pct': float(estimated_exposure / (estimated_exposure + estimated_cash) * 100) if (estimated_exposure + estimated_cash) > 0 else 0
        },
        'quality_metrics': {
            'avg_momentum_score': float(avg_momentum),
            'avg_trade_score': float(avg_trade_score)
        }
    }
    
    return kpi


def calculate_postcast_kpi(orders_file, db_path):
    """
    Calcola KPI per postcast (post-execution)
    
    Metriche:
    - Ordini eseguiti vs proposti
    - Slippage effettivo
    - Costi effettivi vs stimati
    - Performance portfolio post-execution
    - Variazione esposizione
    """
    
    # Carica ordini originali
    with open(orders_file, 'r') as f:
        orders_data = json.load(f)
    
    orders_proposed = orders_data.get('orders', [])
    
    # Connetti al DB
    conn = duckdb.connect(db_path)
    
    # Ottieni ordini eseguiti (ultimi N record dal ledger)
    executed_orders = conn.execute("""
    SELECT 
        symbol, type, qty, price, fees, tax_paid,
        date, notes
    FROM fiscal_ledger
    WHERE run_type = 'PRODUCTION'
    AND type IN ('BUY', 'SELL')
    ORDER BY date DESC, id DESC
    LIMIT ?
    """, [len([o for o in orders_proposed if o['action'] in ['BUY', 'SELL']])]).fetchall()
    
    # Portfolio value post-execution
    portfolio_value = conn.execute("""
    WITH current_positions AS (
        SELECT 
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty
        FROM fiscal_ledger 
        WHERE type IN ('BUY', 'SELL') AND run_type = 'PRODUCTION'
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) > 0
    ),
    current_prices AS (
        SELECT md.symbol, md.close as current_price
        FROM market_data md
        WHERE md.date = (SELECT MAX(date) FROM market_data)
    )
    SELECT COALESCE(SUM(cp.qty * cp2.current_price), 0) as market_value
    FROM current_positions cp
    JOIN current_prices cp2 ON cp.symbol = cp2.symbol
    """).fetchone()[0]
    
    # Cash post-execution
    cash_balance = conn.execute("""
    SELECT COALESCE(SUM(CASE 
        WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
        WHEN type = 'SELL' THEN qty * price - fees - tax_paid
        WHEN type = 'BUY' THEN -(qty * price + fees)
        ELSE 0 
    END), 0) as cash_balance
    FROM fiscal_ledger
    WHERE run_type = 'PRODUCTION'
    """).fetchone()[0]
    
    conn.close()
    
    # Confronta proposti vs eseguiti
    executed_count = len(executed_orders)
    proposed_count = len([o for o in orders_proposed if o['action'] in ['BUY', 'SELL']])
    
    # Calcola slippage e costi
    total_fees_actual = sum(o[4] for o in executed_orders)
    total_tax_actual = sum(o[5] for o in executed_orders)
    total_costs_actual = total_fees_actual + total_tax_actual
    
    total_costs_estimated = sum(
        o.get('fees_est', 0) + o.get('tax_friction_est', 0) 
        for o in orders_proposed if o['action'] in ['BUY', 'SELL']
    )
    
    kpi = {
        'timestamp': datetime.now().isoformat(),
        'type': 'postcast',
        'orders_file': str(orders_file),
        'execution_summary': {
            'orders_proposed': proposed_count,
            'orders_executed': executed_count,
            'execution_rate': float(executed_count / proposed_count * 100) if proposed_count > 0 else 0
        },
        'costs_analysis': {
            'estimated_costs': float(total_costs_estimated),
            'actual_costs': float(total_costs_actual),
            'cost_variance': float(total_costs_actual - total_costs_estimated),
            'cost_variance_pct': float((total_costs_actual - total_costs_estimated) / total_costs_estimated * 100) if total_costs_estimated > 0 else 0
        },
        'portfolio_post_execution': {
            'portfolio_value': float(portfolio_value),
            'cash_balance': float(cash_balance),
            'total_value': float(portfolio_value + cash_balance),
            'exposure_pct': float(portfolio_value / (portfolio_value + cash_balance) * 100) if (portfolio_value + cash_balance) > 0 else 0
        },
        'executed_orders': [
            {
                'symbol': o[0],
                'type': o[1],
                'qty': float(o[2]),
                'price': float(o[3]),
                'fees': float(o[4]),
                'tax': float(o[5]),
                'date': str(o[6])
            }
            for o in executed_orders
        ]
    }
    
    return kpi


def save_production_kpi(kpi_data, kpi_type='forecast'):
    """Salva KPI production su file"""
    pm = get_path_manager()
    
    if kpi_type == 'forecast':
        kpi_file = pm.production_forecast_path()
        # Rinomina da forecast_*.json a kpi_forecast_*.json
        kpi_file = kpi_file.parent / kpi_file.name.replace('forecast_', 'kpi_forecast_')
    else:
        kpi_file = pm.production_postcast_path()
        # Rinomina da postcast_*.json a kpi_postcast_*.json
        kpi_file = kpi_file.parent / kpi_file.name.replace('postcast_', 'kpi_postcast_')
    
    pm.ensure_parent_dir(kpi_file)
    
    with open(kpi_file, 'w') as f:
        json.dump(kpi_data, f, indent=2)
    
    return kpi_file


if __name__ == '__main__':
    # Test con ultimo file orders
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    # Trova ultimo file orders in production
    orders_dir = pm.root / 'data' / 'production' / 'orders'
    if orders_dir.exists():
        orders_files = sorted(orders_dir.glob('orders_*.json'))
        if orders_files:
            latest_orders = orders_files[-1]
            
            print("📊 PRODUCTION KPI CALCULATOR")
            print("=" * 60)
            print(f"Orders file: {latest_orders.name}")
            
            # Calcola forecast KPI
            forecast_kpi = calculate_forecast_kpi(latest_orders, db_path)
            kpi_file = save_production_kpi(forecast_kpi, 'forecast')
            
            print(f"\n✅ Forecast KPI salvato: {kpi_file.name}")
            print(f"   Total orders: {forecast_kpi['orders_summary']['total_orders']}")
            print(f"   Portfolio value: €{forecast_kpi['portfolio']['current_value']:,.2f}")
            print(f"   Estimated exposure: {forecast_kpi['estimated_post_execution']['exposure_pct']:.1f}%")
        else:
            print("❌ Nessun file orders trovato")
    else:
        print("❌ Directory orders non trovata")
