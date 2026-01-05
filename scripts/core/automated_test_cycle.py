#!/usr/bin/env python3
"""
Automated Test Cycle - ETF Italia Project v10
Ciclo automatico di test mirati per ottimizzazione performance
"""

import sys
import os
import duckdb
import json
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_manager import get_session_manager

def automated_test_cycle():
    """Ciclo automatico di test mirati"""
    
    print("🔄 AUTOMATED TEST CYCLE - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Inizializza session manager
    session_manager = get_session_manager()
    
    conn = duckdb.connect(db_path)
    
    try:
        print("🔍 Inizio ciclo test mirati...")
        
        # 1. Test 1: Analisi Volatility Estrema
        print(f"\n📊 TEST 1: ANALISI VOLATILITY ESTREMA")
        
        # Calcola returns prima
        returns_query = """
        WITH daily_returns AS (
            SELECT 
                symbol,
                date,
                adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1 as daily_return
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND adj_close IS NOT NULL
            AND date >= '2010-01-01'
        )
        SELECT 
            symbol,
            STDDEV(daily_return) * SQRT(252) as annual_vol,
            AVG(daily_return) * 252 as annual_ret,
            (EXP(AVG(LN(1 + daily_return)) * 252) - 1) as compound_annual_ret,
            COUNT(*) as data_points
        FROM daily_returns
        WHERE daily_return IS NOT NULL
        GROUP BY symbol
        ORDER BY symbol
        """
        
        volatility_analysis = conn.execute(returns_query).fetchall()
        
        print(f"   📈 Volatility Analysis (2010-2026):")
        for symbol, vol, ret, compound_ret, points in volatility_analysis:
            print(f"      {symbol}:")
            print(f"        Volatility: {vol:.2%}")
            print(f"        Simple Return: {ret:.2%}")
            print(f"        Compound Return: {compound_ret:.2%}")
            print(f"        Data Points: {points:,}")
            print(f"        Vol/Return Ratio: {vol/abs(ret) if ret != 0 else 0:.2f}")
        
        # 2. Test 2: Position Sizing Optimization
        print(f"\n📊 TEST 2: POSITION SIZING OPTIMIZATION")
        
        # Simula diversi position sizing
        sizing_tests = [
            {"name": "Conservative", "max_position": 0.5, "vol_limit": 0.15},
            {"name": "Moderate", "max_position": 0.7, "vol_limit": 0.20},
            {"name": "Aggressive", "max_position": 1.0, "vol_limit": 0.25}
        ]
        
        for test in sizing_tests:
            print(f"   📊 {test['name']} Strategy:")
            print(f"      Max Position: {test['max_position']:.0%}")
            print(f"      Vol Limit: {test['vol_limit']:.0%}")
            
            # Calcola expected performance
            expected_vol = 0.37  # Volatility attuale
            if expected_vol > test['vol_limit']:
                adjusted_position = test['vol_limit'] / expected_vol
                print(f"      Adjusted Position: {adjusted_position:.2%}")
                print(f"      Expected Vol: {test['vol_limit']:.0%}")
            else:
                print(f"      Full Position: {test['max_position']:.0%}")
                print(f"      Expected Vol: {expected_vol:.0%}")
        
        # 3. Test 3: Risk Management Optimization
        print(f"\n📊 TEST 3: RISK MANAGEMENT OPTIMIZATION")
        
        # Analisi drawdown storici
        drawdown_analysis = conn.execute("""
        WITH drawdowns AS (
            SELECT 
                symbol,
                date,
                adj_close,
                MAX(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS UNBOUNDED PRECEDING) as peak,
                (adj_close / MAX(adj_close) OVER (PARTITION BY symbol ORDER BY date ROWS UNBOUNDED PRECEDING)) - 1 as drawdown
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND date >= '2020-01-01'
        )
        SELECT 
            symbol,
            MIN(drawdown) as max_drawdown,
            COUNT(CASE WHEN drawdown < -0.10 THEN 1 END) as dd_10pct_count,
            COUNT(CASE WHEN drawdown < -0.20 THEN 1 END) as dd_20pct_count,
            COUNT(CASE WHEN drawdown < -0.30 THEN 1 END) as dd_30pct_count,
            COUNT(*) as total_days
        FROM drawdowns
        GROUP BY symbol
        ORDER BY symbol
        """).fetchall()
        
        print(f"   📉 Drawdown Analysis (2020-2026):")
        for symbol, max_dd, dd10, dd20, dd30, total in drawdown_analysis:
            print(f"      {symbol}:")
            print(f"        Max Drawdown: {max_dd:.2%}")
            print(f"        Days > -10%: {dd10} ({dd10/total*100:.1f}%)")
            print(f"        Days > -20%: {dd20} ({dd20/total*100:.1f}%)")
            print(f"        Days > -30%: {dd30} ({dd30/total*100:.1f}%)")
        
        # 4. Test 4: Signal Effectiveness
        print(f"\n📊 TEST 4: SIGNAL EFFECTIVENESS")
        
        # Calcola returns prima
        signal_query = """
        WITH market_returns AS (
            SELECT 
                symbol,
                date,
                adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1 as next_day_return
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND date >= '2020-01-01'
        )
        SELECT 
            s.signal_state,
            COUNT(*) as signal_count,
            AVG(mr.next_day_return) as avg_return,
            STDDEV(mr.next_day_return) as return_vol
        FROM signals s
        JOIN market_returns mr ON s.symbol = mr.symbol AND s.date = mr.date - INTERVAL '1 day'
        WHERE s.date >= '2020-01-01'
        GROUP BY s.signal_state
        ORDER BY signal_state
        """
        
        signal_analysis = conn.execute(signal_query).fetchall()
        
        print(f"   📈 Signal Analysis (2020-2026):")
        for signal, count, avg_ret, vol in signal_analysis:
            if signal and avg_ret is not None:
                sharpe = avg_ret / vol if vol != 0 else 0
                print(f"      {signal}:")
                print(f"        Count: {count}")
                print(f"        Avg Return: {avg_ret:.2%}")
                print(f"        Volatility: {vol:.2%}")
                print(f"        Sharpe: {sharpe:.3f}")
        
        # 5. Test 5: Cost Impact Analysis
        print(f"\n📊 TEST 5: COST IMPACT ANALYSIS")
        
        # Simula impact dei costi
        base_return = 0.2282  # 22.82% CAGR attuale
        costs = [
            {"name": "Current", "commission": 0.001, "slippage": 0.0005, "ter": 0.07},
            {"name": "Optimized", "commission": 0.0005, "slippage": 0.0003, "ter": 0.05},
            {"name": "Low Cost", "commission": 0.0003, "slippage": 0.0002, "ter": 0.03}
        ]
        
        for cost in costs:
            # Calcola annual cost impact
            annual_cost = (cost['commission'] * 2) + (cost['slippage'] * 2) + cost['ter']
            net_return = base_return - annual_cost
            
            print(f"   💰 {cost['name']} Costs:")
            print(f"      Commission: {cost['commission']:.2%}")
            print(f"      Slippage: {cost['slippage']:.2%}")
            print(f"      TER: {cost['ter']:.2%}")
            print(f"      Annual Cost: {annual_cost:.2%}")
            print(f"      Net CAGR: {net_return:.2%}")
            print(f"      Cost Impact: {annual_cost/base_return:.1%}")
        
        # 6. Test 6: Regime Detection
        print(f"\n📊 TEST 6: REGIME DETECTION")
        
        # Calcola monthly returns prima
        regime_query = """
        WITH daily_returns AS (
            SELECT 
                symbol,
                date,
                adj_close / LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date) - 1 as daily_return
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
            AND date >= '2020-01-01'
        ),
        monthly_returns AS (
            SELECT 
                symbol,
                DATE_TRUNC('month', date) as month,
                AVG(daily_return) as monthly_return
            FROM daily_returns
            GROUP BY symbol, DATE_TRUNC('month', date)
        ),
        regime_stats AS (
            SELECT 
                symbol,
                AVG(monthly_return) as avg_return,
                STDDEV(monthly_return) as vol,
                COUNT(*) as months
            FROM monthly_returns
            GROUP BY symbol
        )
        SELECT 
            symbol,
            avg_return,
            vol,
            avg_return / vol as sharpe,
            months
        FROM regime_stats
        ORDER BY symbol
        """
        
        regime_analysis = conn.execute(regime_query).fetchall()
        
        print(f"   📊 Regime Analysis (2020-2026):")
        for symbol, avg_ret, vol, sharpe, months in regime_analysis:
            print(f"      {symbol}:")
            print(f"        Avg Monthly Return: {avg_ret:.2%}")
            print(f"        Monthly Vol: {vol:.2%}")
            print(f"        Monthly Sharpe: {sharpe:.3f}")
            print(f"        Months: {months}")
        
        # 7. Generazione report test
        print(f"\n📊 GENERAZIONE REPORT TEST")
        
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_cycle": "automated_optimization",
            "volatility_analysis": [
                {"symbol": row[0], "annual_vol": row[1], "annual_ret": row[2], "data_points": row[3]}
                for row in volatility_analysis
            ],
            "position_sizing": sizing_tests,
            "drawdown_analysis": [
                {"symbol": row[0], "max_drawdown": row[1], "dd_10pct_count": row[2], 
                 "dd_20pct_count": row[3], "dd_30pct_count": row[4], "total_days": row[5]}
                for row in drawdown_analysis
            ],
            "signal_analysis": [
                {"signal": row[0], "count": row[1], "avg_return": row[2], 
                 "volatility": row[3], "sharpe": row[2]/row[3] if row[3] != 0 else 0}
                for row in signal_analysis if row[0] and row[2] is not None
            ],
            "cost_analysis": costs,
            "regime_analysis": [
                {"symbol": row[0], "avg_return": row[1], "vol": row[2], 
                 "sharpe": row[3], "months": row[4]}
                for row in regime_analysis
            ]
        }
        
        # Salva report nella sessione corrente
        report_file = session_manager.add_report_to_session('automated_test_cycle', test_results, 'json')
        
        print(f"   📄 Report salvato: {report_file}")
        
        # 8. Raccomandazioni ottimizzazione
        print(f"\n💡 RACCOMANDAZIONI OTTIMIZZAZIONE:")
        
        print(f"   🎯 VOLATILITY MANAGEMENT:")
        print(f"      • Volatility estrema (37%) richiede position sizing dinamico")
        print(f"      • Implementare volatility targeting: 15-20% max")
        print(f"      • Ridurre posizione quando vol > 25%")
        
        print(f"   📉 DRAWDOWN CONTROL:")
        print(f"      • Max drawdown -90% inaccettabile")
        print(f"      • Implementare stop-loss a -15/-20%")
        print(f"      • Usare trailing stop per proteggere gains")
        
        print(f"   📈 SIGNAL OPTIMIZATION:")
        print(f"      • Analizzare effectiveness segnali RISK_ON")
        print(f"      • Implementare regime-based adjustments")
        print(f"      • Aggiungere mean reversion per diversificazione")
        
        print(f"   💰 COST OPTIMIZATION:")
        print(f"      • Commission: 0.1% → 0.05% (50% reduction)")
        print(f"      • Slippage: 5bps → 3bps (40% reduction)")
        print(f"      • TER: 7% → 5% (29% reduction)")
        print(f"      • Impact previsto: +2-3% CAGR netto")
        
        print(f"   🔧 RISK MANAGEMENT:")
        print(f"      • Position sizing: 50-70% max (vs 100%)")
        print(f"      • Vol limit: 15-20% (vs 37%)")
        print(f"      • Stop-loss: -15/-20% (vs none)")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore test cycle: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = automated_test_cycle()
    sys.exit(0 if success else 1)
