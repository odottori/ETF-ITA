#!/usr/bin/env python3
"""
Performance Report Generator - ETF Italia Project v003
Genera report performance completi da Run Package
"""

import sys
import os
import json
import duckdb

from datetime import datetime, timedelta
import pandas as pd

# Aggiungi path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager
from utils.console_utils import setup_windows_console

# Windows console robustness
setup_windows_console()

def generate_performance_report(db_path, output_dir=None):
    """
    Genera report performance completo
    """
    
    print("📊 PERFORMANCE REPORT GENERATOR")
    print("=" * 50)
    
    if not os.path.exists(db_path):
        print("❌ Database non trovato")
        return False
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Portfolio overview
        print("1️⃣ Analisi portafoglio attuale...")
        portfolio_query = """
        WITH current_positions AS (
            SELECT 
                symbol,
                SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty,
                AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_price
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL')
            GROUP BY symbol
            HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        ),
        current_prices AS (
            SELECT md.symbol, md.close as current_price, md.adj_close as adj_price
            FROM market_data md
            WHERE md.date = (SELECT MAX(date) FROM market_data)
        ),
        portfolio_summary AS (
            SELECT 
                cp.symbol,
                cp.qty,
                cp.avg_price,
                cp2.current_price,
                cp2.adj_price,
                cp.qty * cp2.current_price as market_value,
                cp.qty * (cp2.current_price - cp.avg_price) as unrealized_pnl,
                (cp2.current_price / cp.avg_price - 1) * 100 as return_pct
            FROM current_positions cp
            JOIN current_prices cp2 ON cp.symbol = cp2.symbol
        )
        SELECT 
            symbol,
            qty,
            avg_price,
            current_price,
            market_value,
            unrealized_pnl,
            return_pct
        FROM portfolio_summary
        ORDER BY market_value DESC
        """
        
        portfolio_data = conn.execute(portfolio_query).fetchdf()
        
        # 2. Cash balance
        print("2️⃣ Calcolo cash balance...")
        cash_balance = conn.execute("""
        SELECT COALESCE(SUM(CASE 
            WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
            WHEN type = 'BUY' THEN -(qty * price + fees)
            WHEN type = 'INTEREST' THEN qty
            ELSE 0 
        END), 0) as cash_balance
        FROM fiscal_ledger
        """).fetchone()[0]
        
        # 3. Performance metrics
        print("3️⃣ Calcolo metriche performance...")
        
        # Query semplificata per performance metrics
        perf_query = """
        WITH daily_portfolio_value AS (
            SELECT 
                md.date,
                COALESCE(SUM(CASE 
                    WHEN fl.type = 'DEPOSIT' THEN fl.qty * fl.price - fl.fees - fl.tax_paid
                    WHEN fl.type = 'SELL' THEN fl.qty * fl.price - fl.fees - fl.tax_paid
                    WHEN fl.type = 'BUY' THEN -(fl.qty * fl.price + fl.fees)
                    WHEN fl.type = 'INTEREST' THEN fl.qty
                    ELSE 0 
                END), 0) as cash_balance
            FROM market_data md
            LEFT JOIN fiscal_ledger fl ON md.date >= fl.date AND md.symbol = fl.symbol
            WHERE md.date >= (SELECT MIN(date) FROM fiscal_ledger WHERE type = 'DEPOSIT')
            GROUP BY md.date
        ),
        portfolio_total AS (
            SELECT 
                date,
                cash_balance as total_value
            FROM daily_portfolio_value
        )
        SELECT 
            COUNT(*) as trading_days,
            MIN(total_value) as start_value,
            MAX(total_value) as end_value,
            (MAX(total_value) / MIN(total_value) - 1) as total_return
        FROM portfolio_total
        """
        
        perf_data = conn.execute(perf_query).fetchone()
        
        if perf_data:
            trading_days, start_value, end_value, total_return = perf_data
            
            # Calcoli derivati
            total_return = (end_value / start_value - 1) if start_value > 0 else 0
            annual_return = total_return * (252 / trading_days) if trading_days > 0 else 0
            
            # 4. Tax summary
            print("4️⃣ Riepilogo fiscale...")
            tax_summary = conn.execute("""
            SELECT 
                SUM(CASE WHEN type = 'SELL' THEN (qty * price - fees) ELSE 0 END) as total_sell_proceeds,
                SUM(CASE WHEN type = 'SELL' THEN tax_paid ELSE 0 END) as total_tax_paid,
                SUM(CASE WHEN type = 'SELL' THEN 1 ELSE 0 END) as total_sells,
                SUM(CASE WHEN type = 'BUY' THEN (qty * price + fees) ELSE 0 END) as total_buy_cost
            FROM fiscal_ledger
            WHERE type IN ('BUY', 'SELL')
            """).fetchone()
            
            total_sell_proceeds, total_tax_paid, total_sells, total_buy_cost = tax_summary
            # Stima P&L realizzato (semplificata)
            total_realized_pnl = (total_sell_proceeds or 0) - (total_buy_cost or 0)
            profitable_trades = 0  # Non calcolabile senza tracking trade-by-trade
            losing_trades = 0
            
            # 5. Risk metrics (semplificati)
            print("5️⃣ Calcolo metriche rischio...")
            risk_data = conn.execute("""
            WITH daily_returns AS (
                SELECT 
                    md.date,
                    (md.adj_close / LAG(md.adj_close) OVER (PARTITION BY md.symbol ORDER BY md.date) - 1) as daily_return
                FROM market_data md
                WHERE md.symbol IN (SELECT DISTINCT symbol FROM fiscal_ledger WHERE type IN ('BUY', 'SELL'))
                AND md.date >= (SELECT MIN(date) FROM fiscal_ledger WHERE type = 'DEPOSIT')
                ORDER BY md.symbol, md.date
            ),
            portfolio_returns AS (
                SELECT 
                    date,
                    AVG(daily_return) as portfolio_return
                FROM daily_returns
                WHERE daily_return IS NOT NULL
                GROUP BY date
            )
            SELECT 
                STDDEV(portfolio_return) * SQRT(252) as portfolio_volatility,
                MIN(portfolio_return) as worst_daily_return
            FROM portfolio_returns
            """).fetchone()
            
            portfolio_volatility, worst_daily_ret = risk_data
            
            # 5.5 Emotional Gap (TL-3.2)
            print("💭 Calcolo Emotional Gap (PnL puro vs reale)...")
            
            # Calcola fees totali
            total_fees = conn.execute("""
            SELECT COALESCE(SUM(fees), 0) as total_fees
            FROM fiscal_ledger
            WHERE type IN ('BUY', 'SELL')
            """).fetchone()[0]
            
            # PnL "puro" (senza costi/tasse)
            pnl_pure = total_realized_pnl + (total_fees or 0) + (total_tax_paid or 0)
            
            # PnL "reale" (con costi/tasse)
            pnl_real = total_realized_pnl
            
            # Emotional Gap
            emotional_gap = pnl_real - pnl_pure
            emotional_gap_pct = (emotional_gap / pnl_pure * 100) if pnl_pure != 0 else 0
            
            # 6. Report structure
            report = {
                'timestamp': datetime.now().isoformat(),
                'portfolio_summary': {
                    'total_value': float(end_value + cash_balance) if end_value else cash_balance,
                    'stock_value': float(end_value) if end_value else 0,
                    'cash_balance': float(cash_balance),
                    'positions_count': len(portfolio_data),
                    'positions': portfolio_data.to_dict('records') if not portfolio_data.empty else []
                },
                'performance_metrics': {
                    'total_return_pct': float(total_return * 100),
                    'annual_return_pct': float(annual_return * 100),
                    'annual_volatility_pct': float(portfolio_volatility * 100) if portfolio_volatility else 0,
                    'sharpe_ratio': float(annual_return / (portfolio_volatility if portfolio_volatility else 0.01)) if portfolio_volatility else 0,
                    'max_drawdown_pct': 0.0,  # Semplificato
                    'trading_days': int(trading_days),
                    'start_value': float(start_value) if start_value else 0,
                    'end_value': float(end_value) if end_value else 0,
                    'best_daily_return_pct': 0.0,  # Semplificato
                    'worst_daily_return_pct': float(worst_daily_ret * 100) if worst_daily_ret else 0
                },
                'risk_metrics': {
                    'portfolio_volatility_pct': float(portfolio_volatility * 100) if portfolio_volatility else 0,
                    'worst_daily_return_pct': float(worst_daily_ret * 100) if worst_daily_ret else 0,
                    'var_5_daily_pct': 0.0  # Semplificato
                },
                'tax_summary': {
                    'total_realized_pnl': float(total_realized_pnl) if total_realized_pnl else 0,
                    'total_tax_paid': float(total_tax_paid) if total_tax_paid else 0,
                    'total_fees': float(total_fees) if total_fees else 0,
                    'profitable_trades': int(profitable_trades) if profitable_trades else 0,
                    'losing_trades': int(losing_trades) if losing_trades else 0,
                    'win_rate_pct': float(profitable_trades / (profitable_trades + losing_trades) * 100) if (profitable_trades + losing_trades) > 0 else 0
                },
                'emotional_gap': {
                    'pnl_pure_eur': float(pnl_pure),
                    'pnl_real_eur': float(pnl_real),
                    'gap_eur': float(emotional_gap),
                    'gap_pct': float(emotional_gap_pct),
                    'total_costs_eur': float((total_fees or 0) + (total_tax_paid or 0)),
                    'explanation': 'Gap tra PnL teorico (senza costi) e PnL reale (con fees + tasse)'
                }
            }
            
            # 7. Output
            print(f"💰 Total Portfolio Value: €{report['portfolio_summary']['total_value']:,.2f}")
            print(f"📈 Total Return: {report['performance_metrics']['total_return_pct']:.2f}%")
            print(f"📊 Annual Return: {report['performance_metrics']['annual_return_pct']:.2f}%")
            print(f"⚡ Sharpe Ratio: {report['performance_metrics']['sharpe_ratio']:.2f}")
            print(f"📉 Max Drawdown: {report['performance_metrics']['max_drawdown_pct']:.2f}%")
            print(f"📊 Portfolio Volatility: {report['risk_metrics']['portfolio_volatility_pct']:.2f}%")
            print(f"💸 Total Tax Paid: €{report['tax_summary']['total_tax_paid']:,.2f}")
            print(f"🎯 Win Rate: {report['tax_summary']['win_rate_pct']:.1f}%")
            
            # Emotional Gap warning
            print(f"\n💭 EMOTIONAL GAP ANALYSIS:")
            print(f"   PnL Puro (senza costi): €{report['emotional_gap']['pnl_pure_eur']:,.2f}")
            print(f"   PnL Reale (con costi):  €{report['emotional_gap']['pnl_real_eur']:,.2f}")
            print(f"   Gap (costi totali):     €{report['emotional_gap']['gap_eur']:,.2f} ({report['emotional_gap']['gap_pct']:.1f}%)")
            if report['emotional_gap']['gap_eur'] < -100:
                print(f"   ⚠️  ATTENZIONE: Costi elevati impattano significativamente il rendimento!")
            
            # 8. Save report
            if not output_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"data/reports/sessions/{timestamp}/08_performance"
            
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{output_dir}/performance_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f"📁 Report saved to: {output_file}")
            
            return True
            
        else:
            print("❌ Impossibile calcolare metriche performance")
            return False
            
    except Exception as e:
        print(f"❌ Errore durante generazione report: {e}")
        return False
    finally:
        conn.close()

def main():
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    success = generate_performance_report(db_path)
    
    if success:
        print("\n✅ Performance report generated successfully")
        return 0
    else:
        print("\n❌ Performance report generation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
