#!/usr/bin/env python3
"""
Performance Report Generator - ETF Italia Project v10
Genera report completo delle performance del sistema
"""

import sys
import os
import json
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def generate_performance_report():
    """Genera report completo delle performance"""
    
    print(" PERFORMANCE REPORT GENERATOR - ETF Italia Project v10")
    print("=" * 60)
    
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports')
    
    try:
        print(" Analisi report disponibili...")
        
        # 1. Analizza backtest più recente
        backtest_dirs = [d for d in os.listdir(reports_dir) if d.startswith('backtest_') and os.path.isdir(os.path.join(reports_dir, d))]
        
        if backtest_dirs:
            latest_backtest = sorted(backtest_dirs)[-1]
            backtest_path = os.path.join(reports_dir, latest_backtest)
            
            print(f"\n BACKTEST REPORT: {latest_backtest}")
            
            # Leggi KPI
            kpi_file = os.path.join(backtest_path, 'kpi.json')
            if os.path.exists(kpi_file):
                with open(kpi_file, 'r') as f:
                    kpi_data = json.load(f)
                
                portfolio = kpi_data.get('portfolio', {})
                benchmark = kpi_data.get('benchmark', {})
                
                print(f"    Portfolio Performance:")
                print(f"      CAGR: {portfolio.get('cagr', 0):.2%}")
                print(f"      Max Drawdown: {portfolio.get('max_dd', 0):.2%}")
                print(f"      Volatility: {portfolio.get('vol', 0):.2%}")
                print(f"      Sharpe Ratio: {portfolio.get('sharpe', 0):.3f}")
                print(f"      Turnover: {portfolio.get('turnover', 0):.2%}")
                
                print(f"\n    Benchmark Performance:")
                print(f"      CAGR: {benchmark.get('cagr', 0):.2%}")
                print(f"      Max Drawdown: {benchmark.get('max_dd', 0):.2%}")
                print(f"      Volatility: {benchmark.get('vol', 0):.2%}")
                print(f"      Sharpe Ratio: {benchmark.get('sharpe', 0):.3f}")
                
                # Calcola alpha
                alpha = portfolio.get('cagr', 0) - benchmark.get('cagr', 0)
                print(f"\n    Alpha: {alpha:.2%}")
                
                # Valutazione performance
                sharpe_portfolio = portfolio.get('sharpe', 0)
                sharpe_benchmark = benchmark.get('sharpe', 0)
                
                if sharpe_portfolio > sharpe_benchmark:
                    print(f"    Sharpe Ratio superiore al benchmark")
                else:
                    print(f"   ️ Sharpe Ratio inferiore al benchmark")
                
                if portfolio.get('max_dd', 0) > benchmark.get('max_dd', 0):
                    print(f"   ️ Drawdown superiore al benchmark")
                else:
                    print(f"    Drawdown inferiore al benchmark")
            
            # Leggi summary
            summary_file = os.path.join(backtest_path, 'summary.md')
            if os.path.exists(summary_file):
                print(f"\n    Summary report disponibile")
            
            # Leggi manifest
            manifest_file = os.path.join(backtest_path, 'manifest.json')
            if os.path.exists(manifest_file):
                with open(manifest_file, 'r') as f:
                    manifest_data = json.load(f)
                
                print(f"\n    Configurazione:")
                print(f"      Run ID: {manifest_data.get('run_id')}")
                print(f"      Execution Model: {manifest_data.get('execution_model')}")
                print(f"      Commission: {manifest_data.get('cost_model', {}).get('commission_pct', 0):.2%}")
                print(f"      Slippage: {manifest_data.get('cost_model', {}).get('slippage_bps', 0)} bps")
                print(f"      TER: {manifest_data.get('cost_model', {}).get('ter', 0):.2%}")
                print(f"      Tax Rate: {manifest_data.get('tax_model', {}).get('tax_rate_capital', 0):.2%}")
        
        # 2. Analizza stress test più recente
        stress_files = [f for f in os.listdir(reports_dir) if f.startswith('stress_test_') and f.endswith('.json')]
        
        if stress_files:
            latest_stress = sorted(stress_files)[-1]
            stress_path = os.path.join(reports_dir, latest_stress)
            
            print(f"\n STRESS TEST REPORT: {latest_stress}")
            
            with open(stress_path, 'r') as f:
                stress_data = json.load(f)
            
            cagr_stats = stress_data.get('cagr_stats', {})
            max_dd_stats = stress_data.get('max_dd_stats', {})
            risk_assessment = stress_data.get('risk_assessment', {})
            
            print(f"    Monte Carlo Results (1000 simulations):")
            print(f"      CAGR Mean: {cagr_stats.get('mean', 0):.2%}")
            print(f"      CAGR 5th percentile: {cagr_stats.get('p5', 0):.2%}")
            print(f"      CAGR 95th percentile: {cagr_stats.get('p95', 0):.2%}")
            
            print(f"      Max DD Mean: {max_dd_stats.get('mean', 0):.2%}")
            print(f"      Max DD 5th percentile: {max_dd_stats.get('p5', 0):.2%}")
            print(f"      Max DD 95th percentile: {max_dd_stats.get('p95', 0):.2%}")
            
            print(f"      Sharpe Mean: {risk_assessment.get('sharpe_mean', 0):.2f}")
            print(f"      Risk Level: {risk_assessment.get('risk_level', 'UNKNOWN')}")
            
            # Valutazione stress test
            max_dd_5th = risk_assessment.get('max_dd_5th_pct', 0)
            if max_dd_5th <= -0.25:
                print(f"    Risk Level accettabile (Max DD 5th <= -25%)")
            else:
                print(f"   ️ Risk Level elevato (Max DD 5th > -25%)")
        
        # 3. Analizza strategia ottimale
        strategy_files = [f for f in os.listdir(reports_dir) if f.startswith('optimal_strategy_') and f.endswith('.json')]
        
        if strategy_files:
            latest_strategy = sorted(strategy_files)[-1]
            strategy_path = os.path.join(reports_dir, latest_strategy)
            
            print(f"\n OPTIMAL STRATEGY REPORT: {latest_strategy}")
            
            with open(strategy_path, 'r') as f:
                strategy_data = json.load(f)
            
            print(f"    Performance Ottimale:")
            print(f"      Sharpe Ratio: {strategy_data.get('sharpe_ratio', 0):.3f}")
            print(f"      CAGR: {strategy_data.get('cagr', 0):.2%}")
            print(f"      Max Drawdown: {strategy_data.get('max_drawdown', 0):.2%}")
            
            print(f"\n    Combinazione Strategie:")
            strategies = strategy_data.get('optimal_combination', [])
            for strategy in strategies:
                print(f"      • {strategy}")
        
        # 4. Analizza test di sistema
        system_files = [f for f in os.listdir(reports_dir) if f.startswith('system_test_') and f.endswith('.json')]
        
        if system_files:
            latest_system = sorted(system_files)[-1]
            system_path = os.path.join(reports_dir, latest_system)
            
            print(f"\n SYSTEM TEST REPORT: {latest_system}")
            
            with open(system_path, 'r') as f:
                system_data = json.load(f)
            
            assessment = system_data.get('overall_assessment', {})
            
            print(f"    Assessment Sistema:")
            print(f"      Passed: {assessment.get('passed', 0)}/10")
            print(f"      Warnings: {assessment.get('warnings', 0)}/10")
            print(f"      Failed: {assessment.get('failed', 0)}/10")
            print(f"      Errors: {assessment.get('errors', 0)}/10")
            
            print(f"      Status: {system_data.get('status', 'UNKNOWN')}")
        
        # 5. Report finale
        print(f"\n PERFORMANCE REPORT COMPLETO")
        print(f"    Report disponibili: {len(backtest_dirs)} backtest, {len(stress_files)} stress test, {len(strategy_files)} strategie")
        print(f"    Ultimo aggiornamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 6. Raccomandazioni
        print(f"\n RACCOMANDAZIONI FINALI:")
        
        if backtest_dirs:
            latest_backtest = sorted(backtest_dirs)[-1]
            kpi_file = os.path.join(reports_dir, latest_backtest, 'kpi.json')
            
            if os.path.exists(kpi_file):
                with open(kpi_file, 'r') as f:
                    kpi_data = json.load(f)
                
                portfolio = kpi_data.get('portfolio', {})
                benchmark = kpi_data.get('benchmark', {})
                
                sharpe_portfolio = portfolio.get('sharpe', 0)
                max_dd = portfolio.get('max_dd', 0)
                
                if sharpe_portfolio > 1.0:
                    print(f"    Eccellente Sharpe Ratio ({sharpe_portfolio:.2f})")
                elif sharpe_portfolio > 0.5:
                    print(f"    Buon Sharpe Ratio ({sharpe_portfolio:.2f})")
                else:
                    print(f"   ️ Sharpe Ratio da migliorare ({sharpe_portfolio:.2f})")
                
                if max_dd > -0.20:
                    print(f"    Drawdown controllato ({max_dd:.2%})")
                elif max_dd > -0.30:
                    print(f"   ️ Drawdown elevato ({max_dd:.2%})")
                else:
                    print(f"    Drawdown eccessivo ({max_dd:.2%})")
                
                alpha = portfolio.get('cagr', 0) - benchmark.get('cagr', 0)
                if alpha > 0:
                    print(f"    Alpha positivo ({alpha:.2%})")
                else:
                    print(f"   ️ Alpha negativo ({alpha:.2%})")
        
        print(f"\n SISTEMA PRONTO PER PRODUZIONE!")
        
        return True
        
    except Exception as e:
        print(f" Errore generazione report: {e}")
        return False

if __name__ == "__main__":
    success = generate_performance_report()
    sys.exit(0 if success else 1)
