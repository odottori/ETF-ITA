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
        performance_query = """
        WITH daily_portfolio_value AS (
            SELECT 
                md.date,
                SUM(CASE 
                    WHEN fl.type = 'BUY' THEN fl.qty * md.close
                    WHEN fl.type = 'SELL' THEN -fl.qty * md.close
                    ELSE 0 
                END) as stock_value,
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
                stock_value + cash_balance as total_value
            FROM daily_portfolio_value
        ),
        returns AS (
            SELECT 
                date,
                total_value,
                LAG(total_value) OVER (ORDER BY date) as prev_value,
                (total_value / LAG(total_value) OVER (ORDER BY date) - 1) as daily_return
            FROM portfolio_total
            ORDER BY date
        )
        SELECT 
            COUNT(*) as trading_days,
            FIRST_VALUE(total_value) OVER (ORDER BY date) as start_value,
            LAST_VALUE(total_value) OVER (ORDER BY date) as end_value,
            AVG(daily_return) as avg_daily_return,
            STDDEV(daily_return) as daily_volatility,
            MIN(daily_return) as worst_daily_return,
            MAX(daily_return) as best_daily_return,
            MIN(total_value) as min_value,
            MAX(total_value) as max_value
        FROM returns
        WHERE daily_return IS NOT NULL
        """
        
        perf_data = conn.execute(performance_query).fetchone()
        
        if perf_data:
            trading_days, start_value, end_value, avg_daily_ret, daily_vol, worst_day, best_day, min_val, max_val = perf_data
            
            # Calcoli derivati
            total_return = (end_value / start_value - 1) if start_value > 0 else 0
            annual_return = total_return * (252 / trading_days) if trading_days > 0 else 0
            annual_volatility = daily_vol * (252 ** 0.5) if daily_vol else 0
            sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
            max_drawdown = (max_val - min_val) / max_val if max_val > 0 else 0
            
            # 4. Tax summary
            print("4️⃣ Riepilogo fiscale...")
            tax_summary = conn.execute("""
            SELECT 
                SUM(CASE WHEN type = 'SELL' THEN realized_pnl_eur ELSE 0 END) as total_realized_pnl,
                SUM(CASE WHEN type = 'SELL' THEN tax_paid_eur ELSE 0 END) as total_tax_paid,
                SUM(CASE WHEN type = 'SELL' AND realized_pnl_eur > 0 THEN 1 ELSE 0 END) as profitable_trades,
                SUM(CASE WHEN type = 'SELL' AND realized_pnl_eur <= 0 THEN 1 ELSE 0 END) as losing_trades
            FROM fiscal_ledger
            WHERE type = 'SELL'
            """).fetchone()
            
            total_realized_pnl, total_tax_paid, profitable_trades, losing_trades = tax_summary
            
            # 5. Risk metrics
            print("5️⃣ Calcolo metriche rischio...")
            risk_query = """
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
                MIN(portfolio_return) as worst_daily_return,
                PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY portfolio_return) as var_5_daily
            FROM portfolio_returns
            """
            
            risk_data = conn.execute(risk_query).fetchone()
            portfolio_volatility, worst_daily_ret, var_5_daily = risk_data
            
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
                    'annual_volatility_pct': float(annual_volatility * 100),
                    'sharpe_ratio': float(sharpe_ratio),
                    'max_drawdown_pct': float(max_drawdown * 100),
                    'trading_days': int(trading_days),
                    'start_value': float(start_value) if start_value else 0,
                    'end_value': float(end_value) if end_value else 0,
                    'best_daily_return_pct': float(best_day * 100) if best_day else 0,
                    'worst_daily_return_pct': float(worst_day * 100) if worst_day else 0
                },
                'risk_metrics': {
                    'portfolio_volatility_pct': float(portfolio_volatility * 100) if portfolio_volatility else 0,
                    'worst_daily_return_pct': float(worst_daily_ret * 100) if worst_daily_ret else 0,
                    'var_5_daily_pct': float(var_5_daily * 100) if var_5_daily else 0
                },
                'tax_summary': {
                    'total_realized_pnl': float(total_realized_pnl) if total_realized_pnl else 0,
                    'total_tax_paid': float(total_tax_paid) if total_tax_paid else 0,
                    'profitable_trades': int(profitable_trades) if profitable_trades else 0,
                    'losing_trades': int(losing_trades) if losing_trades else 0,
                    'win_rate_pct': float(profitable_trades / (profitable_trades + losing_trades) * 100) if (profitable_trades + losing_trades) > 0 else 0
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
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    success = generate_performance_report(db_path)
    
    if success:
        print("\n✅ Performance report generated successfully")
        return 0
    else:
        print("\n❌ Performance report generation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
