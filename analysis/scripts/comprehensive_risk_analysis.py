#!/usr/bin/env python3
"""
Comprehensive Risk Analysis - ETF Italia Project v10
Analisi completa del rischio con correlazione e volatility clustering
"""

import sys
import os
import duckdb
import json
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def comprehensive_risk_analysis():
    """Analisi completa del rischio"""
    
    print(" COMPREHENSIVE RISK ANALYSIS - ETF Italia Project v10")
    print("=" * 70)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports')
    
    # Verifica che il database esista
    if not os.path.exists(db_path):
        print(f" Database non trovato: {db_path}")
        return False, None
    
    conn = duckdb.connect(db_path)
    
    try:
        print(" Inizio analisi rischio completa...")
        
        # 1. Correlation Analysis
        print(f"\n 1. CORRELATION ANALYSIS")
        
        correlation_query = """
        WITH daily_returns AS (
            SELECT 
                date,
                symbol,
                adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1 as daily_return
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND adj_close IS NOT NULL
            AND date >= '2010-01-01'
        ),
        pivot_returns AS (
            SELECT 
                date,
                MAX(CASE WHEN symbol = 'CSSPX.MI' THEN daily_return END) as csspx_return,
                MAX(CASE WHEN symbol = 'XS2L.MI' THEN daily_return END) as xs2l_return
            FROM daily_returns
            GROUP BY date
            HAVING csspx_return IS NOT NULL AND xs2l_return IS NOT NULL
        )
        SELECT 
            CORR(csspx_return, xs2l_return) as correlation,
            COUNT(*) as data_points,
            STDDEV(csspx_return) as csspx_vol,
            STDDEV(xs2l_return) as xs2l_vol,
            AVG(csspx_return) as csspx_avg,
            AVG(xs2l_return) as xs2l_avg
        FROM pivot_returns
        """
        
        corr_results = conn.execute(correlation_query).fetchall()
        
        for corr, points, csspx_vol, xs2l_vol, csspx_avg, xs2l_avg in corr_results:
            print(f"    Correlazione CSSPX-XS2L: {corr:.3f}")
            print(f"    Data Points: {points:,}")
            print(f"    CSSPX Vol: {csspx_vol*100:.2f}%")
            print(f"    XS2L Vol: {xs2l_vol*100:.2f}%")
            
            # Risk level assessment
            if corr > 0.8:
                risk_level = "HIGH"
                risk_desc = "Correlazione molto alta - bassa diversificazione"
            elif corr > 0.6:
                risk_level = "MEDIUM"
                risk_desc = "Correlazione moderata - diversificazione limitata"
            else:
                risk_level = "LOW"
                risk_desc = "Correlazione bassa - buona diversificazione"
            
            print(f"   RISK LEVEL: {risk_level}")
            print(f"    Descrizione: {risk_desc}")
        
        # 2. Volatility Clustering Analysis
        print(f"\n 2. VOLATILITY CLUSTERING ANALYSIS")
        
        volatility_clustering_query = """
        WITH daily_returns AS (
            SELECT 
                symbol,
                date,
                adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1 as daily_return,
                ABS(adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1) as abs_return
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND adj_close IS NOT NULL
            AND date >= '2020-01-01'
        ),
        volatility_regime AS (
            SELECT 
                symbol,
                date,
                daily_return,
                abs_return,
                AVG(abs_return) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as rolling_vol_21d,
                CASE 
                    WHEN AVG(abs_return) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) > 
                         (SELECT AVG(abs_return) * 1.5 FROM daily_returns dr WHERE dr.symbol = daily_returns.symbol) 
                    THEN 'HIGH_VOL'
                    WHEN AVG(abs_return) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) < 
                         (SELECT AVG(abs_return) * 0.7 FROM daily_returns dr WHERE dr.symbol = daily_returns.symbol) 
                    THEN 'LOW_VOL'
                    ELSE 'NORMAL_VOL'
                END as vol_regime
            FROM daily_returns
        )
        SELECT 
            symbol,
            vol_regime,
            COUNT(*) as days_in_regime,
            AVG(abs_return) as avg_vol,
            STDDEV(daily_return) as return_vol,
            AVG(daily_return) as avg_return
        FROM volatility_regime
        GROUP BY symbol, vol_regime
        ORDER BY symbol, vol_regime
        """
        
        vol_clustering_results = conn.execute(volatility_clustering_query).fetchall()
        
        print(f"    Volatility Regime Analysis (2020-2026):")
        for symbol, regime, days, avg_vol, return_vol, avg_ret in vol_clustering_results:
            pct_days = days / 1286 * 100  # Total trading days 2020-2026
            print(f"      {symbol} - {regime}:")
            print(f"        Days: {days} ({pct_days:.1f}%)")
            print(f"        Avg Vol: {avg_vol*100:.2f}%")
            print(f"        Return Vol: {return_vol*100:.2f}%")
            print(f"        Avg Return: {avg_ret*100:.2f}%")
        
        # 3. Portfolio Risk Metrics
        print(f"\n 3. PORTFOLIO RISK METRICS")
        
        portfolio_query = """
        WITH daily_returns AS (
            SELECT 
                date,
                symbol,
                adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1 as daily_return
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND adj_close IS NOT NULL
            AND date >= '2020-01-01'
        ),
        portfolio_returns AS (
            SELECT 
                date,
                AVG(daily_return) as portfolio_return,
                STDDEV(daily_return) as daily_vol
            FROM daily_returns
            GROUP BY date
        ),
        portfolio_stats AS (
            SELECT 
                AVG(portfolio_return) as avg_daily_return,
                STDDEV(portfolio_return) as portfolio_vol,
                COUNT(*) as trading_days
            FROM portfolio_returns
        )
        SELECT 
            avg_daily_return * 252 as annual_return,
            portfolio_vol * SQRT(252) as annual_vol,
            avg_daily_return * 252 / (portfolio_vol * SQRT(252)) as sharpe_ratio,
            trading_days
        FROM portfolio_stats
        """
        
        portfolio_results = conn.execute(portfolio_query).fetchall()
        
        for ann_ret, ann_vol, sharpe, days in portfolio_results:
            print(f"    Portfolio Performance (2020-2026):")
            print(f"      Annual Return: {ann_ret*100:.2f}%")
            print(f"      Annual Volatility: {ann_vol*100:.2f}%")
            print(f"      Sharpe Ratio: {sharpe:.3f}")
            print(f"      Trading Days: {days:,}")
            
            # Risk assessment
            if ann_vol > 0.25:
                vol_risk = "HIGH"
            elif ann_vol > 0.20:
                vol_risk = "MEDIUM"
            else:
                vol_risk = "LOW"
            
            print(f"      Volatility Risk: {vol_risk}")
        
        # 4. Drawdown Analysis
        print(f"\n 4. DRAWDOWN ANALYSIS")
        
        drawdown_query = """
        WITH daily_prices AS (
            SELECT 
                symbol,
                date,
                adj_close
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND adj_close IS NOT NULL
            AND date >= '2020-01-01'
        ),
        drawdowns AS (
            SELECT 
                symbol,
                date,
                adj_close,
                MAX(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS UNBOUNDED PRECEDING) as peak,
                (adj_close / MAX(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS UNBOUNDED PRECEDING)) - 1 as drawdown
            FROM daily_prices
        ),
        drawdown_stats AS (
            SELECT 
                symbol,
                MIN(drawdown) as max_drawdown,
                COUNT(CASE WHEN drawdown < -0.05 THEN 1 END) as dd_5pct_days,
                COUNT(CASE WHEN drawdown < -0.10 THEN 1 END) as dd_10pct_days,
                COUNT(CASE WHEN drawdown < -0.15 THEN 1 END) as dd_15pct_days,
                COUNT(CASE WHEN drawdown < -0.20 THEN 1 END) as dd_20pct_days,
                COUNT(*) as total_days
            FROM drawdowns
            GROUP BY symbol
        )
        SELECT 
            symbol,
            max_drawdown,
            dd_5pct_days,
            dd_10pct_days,
            dd_15pct_days,
            dd_20pct_days,
            total_days,
            dd_5pct_days * 100.0 / total_days as pct_5pct,
            dd_10pct_days * 100.0 / total_days as pct_10pct,
            dd_15pct_days * 100.0 / total_days as pct_15pct,
            dd_20pct_days * 100.0 / total_days as pct_20pct
        FROM drawdown_stats
        ORDER BY symbol
        """
        
        dd_results = conn.execute(drawdown_query).fetchall()
        
        print(f"    Drawdown Statistics (2020-2026):")
        for symbol, max_dd, dd5, dd10, dd15, dd20, total, pct5, pct10, pct15, pct20 in dd_results:
            print(f"      {symbol}:")
            print(f"        Max Drawdown: {max_dd*100:.2f}%")
            print(f"        Days > -5%: {dd5} ({pct5:.1f}%)")
            print(f"        Days > -10%: {dd10} ({pct10:.1f}%)")
            print(f"        Days > -15%: {dd15} ({pct15:.1f}%)")
            print(f"        Days > -20%: {dd20} ({pct20:.1f}%)")
            
            # Drawdown risk assessment
            if max_dd < -0.30:
                dd_risk = "CRITICAL"
            elif max_dd < -0.20:
                dd_risk = "HIGH"
            elif max_dd < -0.15:
                dd_risk = "MEDIUM"
            else:
                dd_risk = "LOW"
            
            print(f"        Drawdown Risk: {dd_risk}")
        
        # 5. Risk Recommendations
        print(f"\n 5. RISK MANAGEMENT RECOMMENDATIONS")
        
        # Calculate overall risk score
        risk_factors = {
            "correlation": corr if corr else 0.8,  # Default high correlation
            "volatility": ann_vol if ann_vol else 0.26,  # Default high volatility
            "drawdown": max(abs(row[1]) for row in dd_results) if dd_results else 0.59  # Worst drawdown
        }
        
        overall_risk_score = (risk_factors["correlation"] * 0.3 + 
                            risk_factors["volatility"] * 0.4 + 
                            risk_factors["drawdown"] * 0.3)
        
        if overall_risk_score > 0.7:
            overall_risk = "CRITICAL"
            color = ""
        elif overall_risk_score > 0.5:
            overall_risk = "HIGH"
            color = ""
        elif overall_risk_score > 0.3:
            overall_risk = "MEDIUM"
            color = ""
        else:
            overall_risk = "LOW"
            color = ""
        
        print(f"   {color} OVERALL RISK ASSESSMENT: {overall_risk}")
        print(f"    Risk Score: {overall_risk_score:.3f}")
        print(f"    Correlation Factor: {risk_factors['correlation']:.3f}")
        print(f"    Volatility Factor: {risk_factors['volatility']:.3f}")
        print(f"    Drawdown Factor: {risk_factors['drawdown']:.3f}")
        
        print(f"\n    IMMEDIATE ACTIONS REQUIRED:")
        
        if risk_factors["correlation"] > 0.8:
            print(f"       HIGH CORRELATION ({risk_factors['correlation']:.3f}):")
            print(f"         • Ridurre esposizione a 50-60% per ETF")
            print(f"         • Considerare asset class diversification")
            print(f"         • Implementare decorrelation strategy")
        
        if risk_factors["volatility"] > 0.25:
            print(f"       HIGH VOLATILITY ({risk_factors['volatility']:.1%}):")
            print(f"         • Implementare volatility targeting (15-20% max)")
            print(f"         • Position sizing dinamico basato su VIX")
            print(f"         • Stop-loss automatici a -15%")
        
        if risk_factors["drawdown"] < -0.30:
            print(f"       SEVERE DRAWDOWN ({risk_factors['drawdown']:.1%}):")
            print(f"         • Implementare trailing stop-loss")
            print(f"         • Risk-off regime detection")
            print(f"         • Capital preservation priorità")
        
        print(f"\n   RISK MITIGATION STRATEGY:")
        print(f"      1. Position Sizing: Max 50% per ETF")
        print(f"      2. Volatility Target: 15-20% annualizzato")
        print(f"      3. Stop-Loss: -15% absolute, -10% trailing")
        print(f"      4. Rebalancing: Mensile o quando deviazione > 5%")
        print(f"      5. Cash Reserve: 10-15% per opportunità")
        
        # 6. Generate comprehensive report
        print(f"\n 6. GENERAZIONE REPORT COMPLETO")
        
        risk_report = {
            "timestamp": datetime.now().isoformat(),
            "analysis_type": "comprehensive_risk_analysis",
            "overall_risk_level": overall_risk,
            "risk_score": overall_risk_score,
            "correlation_analysis": {
                "correlation": corr if corr else 0.8,
                "data_points": points if 'points' in locals() else 0,
                "risk_level": risk_level if 'risk_level' in locals() else "HIGH"
            },
            "volatility_clustering": [
                {
                    "symbol": row[0],
                    "regime": row[1],
                    "days": row[2],
                    "avg_vol": row[3],
                    "return_vol": row[4],
                    "avg_return": row[5]
                }
                for row in vol_clustering_results
            ],
            "portfolio_metrics": {
                "annual_return": ann_ret if 'ann_ret' in locals() else 0,
                "annual_volatility": ann_vol if 'ann_vol' in locals() else 0.26,
                "sharpe_ratio": sharpe if 'sharpe' in locals() else 0
            },
            "drawdown_analysis": [
                {
                    "symbol": row[0],
                    "max_drawdown": row[1],
                    "dd_5pct_days": row[2],
                    "dd_10pct_days": row[3],
                    "dd_15pct_days": row[4],
                    "dd_20pct_days": row[5],
                    "total_days": row[6]
                }
                for row in dd_results
            ],
            "risk_factors": risk_factors,
            "recommendations": {
                "position_sizing": "50-60% max per ETF",
                "volatility_target": "15-20% annualized",
                "stop_loss": "-15% absolute, -10% trailing",
                "rebalancing": "Monthly or 5% deviation",
                "cash_reserve": "10-15% for opportunities"
            }
        }
        
        # Create session directory with new structure
        session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports', 'sessions', session_timestamp)
        analysis_dir = os.path.join(session_dir, 'analysis')
        
        # Create directories
        os.makedirs(analysis_dir, exist_ok=True)
        
        # Create session info
        session_info = {
            "session_id": session_timestamp,
            "timestamp": datetime.now().isoformat(),
            "analysis_type": "comprehensive_risk_analysis",
            "script": "comprehensive_risk_analysis.py",
            "status": "completed"
        }
        
        session_info_file = os.path.join(session_dir, 'session_info.json')
        with open(session_info_file, 'w') as f:
            json.dump(session_info, f, indent=2)
        
        # Save comprehensive report in analysis subfolder
        report_file = os.path.join(analysis_dir, 'comprehensive_risk_analysis.json')
        
        with open(report_file, 'w') as f:
            json.dump(risk_report, f, indent=2)
        
        print(f"    Report completo salvato: {report_file}")
        
        return True, risk_report
        
    except Exception as e:
        print(f" Errore analisi rischio: {e}")
        return False, None
        
    finally:
        conn.close()

if __name__ == "__main__":
    success, report = comprehensive_risk_analysis()
    sys.exit(0 if success else 1)
