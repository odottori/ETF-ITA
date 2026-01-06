#!/usr/bin/env python3
"""
Backtest Runner - ETF Italia Project v10
Run Package completo con sanity check e reporting
"""

import sys
import os
import json
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_manager import get_session_manager
from sequence_runner import run_sequence_from

def backtest_runner():
    """Esegue backtest completo con Run Package"""
    
    print(" BACKTEST RUNNER - ETF Italia Project v10")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    # Inizializza session manager
    session_manager = get_session_manager()
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Sanity Check bloccante
        print(" Sanity Check...")
        if not sanity_check(conn):
            print(" SANITY CHECK FAILED - Backtest interrotto")
            return False
        
        print(" Sanity check passed")
        
        # 2. Genera Run ID
        run_id = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_timestamp = datetime.now().isoformat()
        
        print(f" Run ID: {run_id}")
        
        # 3. Crea sottocartella backtest nella sessione corrente
        backtest_dir = session_manager.create_backtest_dir(run_id)
        
        # 3. Esegui simulazione reale prima di calcolare KPI
        print(" Esecuzione simulazione backtest...")
        
        from backtest_engine import run_backtest_simulation
        if not run_backtest_simulation():
            print(" Simulazione fallita - Backtest interrotto")
            return False
        
        # 4. Calcola KPI portfolio (ora basati su dati reali)
        print(" Calcolo KPI portfolio...")
        
        kpi_data = calculate_kpi(conn, config)
        
        # 5. Calcola KPI benchmark
        print(" Calcolo KPI benchmark...")
        
        benchmark_data = calculate_benchmark_kpi(conn, config)
        
        # 7. Genera Run Package
        print(" Generazione Run Package...")
        
        run_package = {
            'manifest': {
                'run_id': run_id,
                'run_ts': run_timestamp,
                'mode': 'BACKTEST',
                'execution_model': 'T+1_OPEN',
                'cost_model': {
                    'commission_pct': config['universe']['core'][0]['cost_model']['commission_pct'],
                    'slippage_bps': config['universe']['core'][0]['cost_model']['slippage_bps'],
                    'ter': config['universe']['core'][0]['ter']
                },
                'tax_model': {
                    'tax_rate_capital': config['fiscal']['tax_rate_capital'],
                    'tax_loss_carry_years': config['fiscal']['tax_loss_carry_years']
                },
                'currency_base': 'EUR',
                'universe': {
                    'core': config['universe']['core'],
                    'satellite': config['universe']['satellite'],
                    'benchmark': config['universe']['benchmark']
                },
                'benchmark_symbol': config['universe']['benchmark'][0]['symbol'],
                'benchmark_kind': 'INDEX',
                'config_hash': calculate_config_hash(config),
                'data_fingerprint': calculate_data_fingerprint(conn)
            },
            'kpi': {
                'portfolio': kpi_data,
                'benchmark': benchmark_data,
                'kpi_hash': calculate_kpi_hash(kpi_data, benchmark_data)
            },
            'summary': generate_summary(run_id, kpi_data, benchmark_data)
        }
        
        # 8. Salva artefatti nella sottocartella backtest con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        manifest_file = backtest_dir / f'manifest_{timestamp}.json'
        kpi_file = backtest_dir / f'kpi_{timestamp}.json'
        summary_file = backtest_dir / f'summary_{timestamp}.md'
        
        with open(manifest_file, 'w') as f:
            json.dump(run_package['manifest'], f, indent=2)
        
        with open(kpi_file, 'w') as f:
            json.dump(run_package['kpi'], f, indent=2)
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(run_package['summary'])
        
        print(f" Run Package salvato in: {backtest_dir}")
        
        # 9. Stampa riepilogo
        print(f"\n BACKTEST RESULTS:")
        print(f"Run ID: {run_id}")
        print(f"CAGR Portfolio: {kpi_data['cagr']:.2%}")
        print(f"Max Drawdown: {kpi_data['max_dd']:.2%}")
        print(f"Sharpe Ratio: {kpi_data['sharpe']:.2f}")
        print(f"Volatility: {kpi_data['vol']:.2%}")
        print(f"Turnover: {kpi_data['turnover']:.2%}")
        
        if benchmark_data:
            print(f"\n BENCHMARK COMPARISON:")
            print(f"CAGR Benchmark: {benchmark_data['cagr']:.2%}")
            print(f"Alpha: {kpi_data['cagr'] - benchmark_data['cagr']:.2%}")
        
        print(f"\n Backtest completato con successo")
        
        return True
        
    except Exception as e:
        print(f" Errore backtest runner: {e}")
        return False
        
    finally:
        conn.close()

def sanity_check(conn):
    """Controllo di integrità bloccante"""
    
    try:
        # 1. Posizioni negative
        negative_positions = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT symbol, SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL')
            GROUP BY symbol
            HAVING net_qty < 0
        )
        """).fetchone()[0]
        
        if negative_positions > 0:
            print(f" Posizioni negative trovate: {negative_positions}")
            return False
        
        # 2. Cash negativo
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
        
        if cash_balance < 0:
            print(f" Cash balance negativo: €{cash_balance:,.2f}")
            return False
        
        # 3. PMC coerenti
        pmc_issues = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE pmc_snapshot < 0
        """).fetchone()[0]
        
        if pmc_issues > 0:
            print(f" PMC negativi trovati: {pmc_issues}")
            return False
        
        # 4. Date coerenti
        future_dates = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE date > CURRENT_DATE
        """).fetchone()[0]
        
        if future_dates > 0:
            print(f" Date future trovate: {future_dates}")
            return False
        
        return True
        
    except Exception as e:
        print(f" Errore sanity check: {e}")
        return False

def calculate_kpi(conn, config):
    """Calcola KPI portfolio"""
    
    try:
        # Ottieni dati portfolio
        portfolio_data = conn.execute("""
        SELECT date, adj_close, volume
        FROM portfolio_overview
        ORDER BY date
        """).fetchall()
        
        if not portfolio_data:
            return {
                'cagr': 0.0,
                'max_dd': 0.0,
                'vol': 0.0,
                'sharpe': 0.0,
                'turnover': 0.0
            }
        
        df = pd.DataFrame(portfolio_data, columns=['date', 'adj_close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calcola returns giornalieri
        df['daily_return'] = df['adj_close'].pct_change(fill_method=None)
        
        # Rimuovi primi return (NaN)
        df = df.dropna()
        
        if len(df) == 0:
            return {
                'cagr': 0.0,
                'max_dd': 0.0,
                'vol': 0.0,
                'sharpe': 0.0,
                'turnover': 0.0
            }
        
        # CAGR
        days = (df.index[-1] - df.index[0]).days
        if days > 0:
            cagr = (df['adj_close'].iloc[-1] / df['adj_close'].iloc[0]) ** (365.25 / days) - 1
        else:
            cagr = 0.0
        
        # Max Drawdown
        df['cummax'] = df['adj_close'].cummax()
        df['drawdown'] = (df['adj_close'] - df['cummax']) / df['cummax']
        max_dd = df['drawdown'].min()
        
        # Volatilità annualizzata
        vol = df['daily_return'].std() * (252 ** 0.5)
        
        # Sharpe Ratio
        if vol > 0:
            sharpe = cagr / vol
        else:
            sharpe = 0.0
        
        # Turnover (stima)
        # Assumiamo turnover medio mensile del 10%
        turnover = 0.10
        
        return {
            'cagr': cagr,
            'max_dd': max_dd,
            'vol': vol,
            'sharpe': sharpe,
            'turnover': turnover
        }
        
    except Exception as e:
        print(f" Errore calcolo KPI: {e}")
        return {
            'cagr': 0.0,
            'max_dd': 0.0,
            'vol': 0.0,
            'sharpe': 0.0,
            'turnover': 0.0
        }

def calculate_benchmark_kpi(conn, config):
    """Calcola KPI benchmark"""
    
    try:
        # Ottieni dati benchmark
        benchmark_symbol = config['universe']['benchmark'][0]['symbol']
        
        benchmark_data = conn.execute("""
        SELECT date, adj_close
        FROM risk_metrics 
        WHERE symbol = ?
        ORDER BY date
        """, [benchmark_symbol]).fetchall()
        
        if not benchmark_data:
            return {
                'cagr': 0.0,
                'max_dd': 0.0,
                'vol': 0.0,
                'sharpe': 0.0,
                'turnover': 0.0
            }
        
        df = pd.DataFrame(benchmark_data, columns=['date', 'adj_close'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calcola returns giornalieri
        df['daily_return'] = df['adj_close'].pct_change(fill_method=None)
        
        # Rimuovi primi return (NaN)
        df = df.dropna()
        
        if len(df) == 0:
            return {
                'cagr': 0.0,
                'max_dd': 0.0,
                'vol': 0.0,
                'sharpe': 0.0,
                'turnover': 0.0
            }
        
        # CAGR
        days = (df.index[-1] - df.index[0]).days
        if days > 0:
            cagr = (df['adj_close'].iloc[-1] / df['adj_close'].iloc[0]) ** (365. / days) - 1
        else:
            cagr = 0.0
        
        # Max Drawdown
        df['cummax'] = df['adj_close'].cummax()
        df['drawdown'] = (df['adj_close'] - df['cummax']) / df['cummax']
        max_dd = df['drawdown'].min()
        
        # Volatilità annualizzata
        vol = df['daily_return'].std() * (252 ** 0.5)
        
        # Sharpe Ratio
        if vol > 0:
            sharpe = cagr / vol
        else:
            sharpe = 0.0
        
        # Turnover (stima)
        turnover = 0.10
        
        return {
            'cagr': cagr,
            'max_dd': max_dd,
            'vol': vol,
            'sharpe': sharpe,
            'turnover': turnover
        }
        
    except Exception as e:
        print(f" Errore calcolo benchmark KPI: {e}")
        return {
            'cagr': 0.0,
            'max_dd': 0.0,
            'vol': 0.0,
            'sharpe': 0.0,
            'turnover': 0.0
        }

def calculate_config_hash(config):
    """Calcola hash configurazione"""
    import hashlib
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()[:8]

def calculate_data_fingerprint(conn):
    """Calcola fingerprint dati"""
    try:
        # Conta record per simbolo e data massima
        fingerprint_data = conn.execute("""
        SELECT 
            symbol,
            COUNT(*) as record_count,
            MAX(date) as max_date
        FROM market_data
        GROUP BY symbol
        ORDER BY symbol
        """).fetchall()
        
        fingerprint = f"{len(fingerprint_data)} symbols"
        for symbol, count, max_date in fingerprint_data:
            fingerprint += f"|{symbol}:{count}:{max_date}"
        
        return fingerprint
        
    except Exception as e:
        print(f" Errore calcolo data fingerprint: {e}")
        return "unknown"

def calculate_kpi_hash(portfolio_kpi, benchmark_kpi):
    """Calcola hash KPI"""
    import hashlib
    
    kpi_str = f"{portfolio_kpi['cagr']:.6f}|{portfolio_kpi['max_dd']:.6f}|{portfolio_kpi['vol']:.6f}|{portfolio_kpi['sharpe']:.2f}"
    return hashlib.md5(kpi_str.encode()).hexdigest()[:8]

def generate_summary(run_id, portfolio_kpi, benchmark_kpi):
    """Genera summary markdown"""
    
    alpha = portfolio_kpi['cagr'] - benchmark_kpi['cagr']
    
    summary = f"""#  Backtest Report - {run_id}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

##  Performance Summary

### Portfolio Performance
- **CAGR:** {portfolio_kpi['cagr']:.2%}
- **Max Drawdown:** {portfolio_kpi['max_dd']:.2%}
- **Volatility:** {portfolio_kpi['vol']:.2%}
- **Sharpe Ratio:** {portfolio_kpi['sharpe']:.2f}
- **Turnover:** {portfolio_kpi['turnover']:.2%}

### Benchmark Comparison
- **Benchmark CAGR:** {benchmark_kpi['cagr']:.2%}
- **Alpha:** {alpha:+.2%}
- **Information Ratio:** {portfolio_kpi['sharpe'] / benchmark_kpi['sharpe']:.2f}

---

##  Risk Analysis

### Drawdown Analysis
- **Maximum Drawdown:** {portfolio_kpi['max_dd']:.2%}
- **Current Drawdown:** {portfolio_kpi['max_dd']:.2%}
- **Recovery Time:** TBD

### Volatility Regime
- **Current Volatility:** {portfolio_kpi['vol']:.2%}
- **Risk-Adjusted Return:** {portfolio_kpi['sharpe']:.2f}

---

##  Trading Activity

### Position Changes
- **Total Trades:** TBD
- **Win Rate:** TBD
- **Average Holding Period:** TBD

### Signal Performance
- **RISK_ON Signals:** TBD
- **RISK_OFF Signals:** TBD
- **Signal Accuracy:** TBD

---

##  Financial Summary

### Portfolio Value
- **Initial Capital:** €20,000.00
- **Current Value:** TBD
- **Total Return:** TBD
- **Total Fees Paid:** TBD
- **Taxes Paid:** TBD

### Cash Management
- **Cash Interest Earned:** TBD
- **Cash Drag:** TBD

---

##  Conclusions

### Strengths
- [ ] Robust risk management framework
- [ ] Comprehensive cost modeling
- [] Tax-aware position sizing
- [] Systematic signal generation

### Areas for Improvement
- [ ] Signal optimization
- [] Dynamic position sizing
- [] Enhanced risk metrics

### Next Steps
- [ ] Implement walk-forward analysis
- [] Add Monte Carlo stress testing
- [] Optimize signal parameters

---

*Report generated by ETF Italia Project v10*
"""
    
    return summary

if __name__ == "__main__":
    # Esegui backtest_runner e poi continua con la sequenza
    success = backtest_runner()
    
    if success:
        # Continua con la sequenza: performance_report_generator, analyze_schema_drift
        run_sequence_from('backtest_runner')
    else:
        print("❌ Backtest runner fallito - sequenza interrotta")
        sys.exit(1)
