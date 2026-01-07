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
import argparse
import io

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager

# Windows console robustness (avoid UnicodeEncodeError on cp1252)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Fallback (some Windows terminals ignore reconfigure)
try:
    if getattr(sys.stdout, "encoding", None) and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    if getattr(sys.stderr, "encoding", None) and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

from session_manager import get_session_manager

PRESET_PERIODS = {
    'full': ('DYNAMIC', 'DYNAMIC'),
    'recent': ('DYNAMIC', 'DYNAMIC'),
    'covid': ('2020-01-01', '2021-12-31'),
    'gfc': ('2007-01-01', '2010-12-31'),
    'eurocrisis': ('2011-01-01', '2013-12-31'),
    'inflation2022': ('2021-10-01', '2023-03-31'),
}


def _parse_date(s):
    if s is None:
        return None
    return datetime.strptime(s, '%Y-%m-%d').date()


def backtest_runner(start_date=None, end_date=None, preset=None, recent_days=365, run_id_override=None):
    """Esegue backtest completo con Run Package
    
    Args:
        run_id_override: Se fornito, usa questo run_id invece di generarne uno nuovo.
                        Utile per modalità --all per avere run_id distinti per preset.
    """
    
    print(" BACKTEST RUNNER - ETF Italia Project v10")
    print("=" * 60)
    
    pm = get_path_manager()
    config_path = str(pm.etf_universe_path)
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # 0. Pulisci record backtest precedenti
        print(" Pulizia record backtest precedenti...")
        
        # Pulisci fiscal_ledger e orders che hanno run_type
        conn.execute("DELETE FROM fiscal_ledger WHERE run_type = 'BACKTEST'")
        conn.execute("DELETE FROM orders WHERE notes LIKE '%backtest%'")
        
        # Pulisci signals (non ha run_type, pulisco per explain_code)
        conn.execute("DELETE FROM signals WHERE explain_code = 'BACKTEST_SIGNAL'")
        
        conn.commit()
        print(" Record backtest puliti")
        
        # 1. Sanity Check bloccante
        print(" Sanity Check...")
        if not sanity_check(conn):
            print(" SANITY CHECK FAILED - Backtest interrotto")
            return False
        
        print(" Sanity check passed")
        
        # 2. Genera Run ID (usa override se fornito per --all mode)
        if run_id_override:
            run_id = run_id_override
        else:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_id = f"backtest_{ts}" if not preset else f"backtest_{preset}_{ts}"
        
        run_timestamp = datetime.now().isoformat()
        
        print(f" Run ID: {run_id}")
        
        # 3. Ottieni session manager per salvare report
        session_manager = get_session_manager(script_name='backtest_runner')
        
        # 3. Esegui simulazione reale prima di calcolare KPI
        print(" Esecuzione simulazione backtest...")
        
        # Passo parametri al backtest_engine via env (riduce cambiamenti e mantiene compatibilità)
        # Pulisci env per evitare bleed tra run
        for k in ['ETF_ITA_PRESET', 'ETF_ITA_START_DATE', 'ETF_ITA_END_DATE', 'ETF_ITA_RECENT_DAYS']:
            os.environ.pop(k, None)

        if preset:
            os.environ['ETF_ITA_PRESET'] = preset
            if preset == 'recent':
                os.environ['ETF_ITA_RECENT_DAYS'] = str(int(recent_days))
        elif start_date is not None and end_date is not None:
            os.environ['ETF_ITA_START_DATE'] = start_date.strftime('%Y-%m-%d')
            os.environ['ETF_ITA_END_DATE'] = end_date.strftime('%Y-%m-%d')

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
        
        # 8. Salva artefatti nella sessione corrente
        manifest_file = session_manager.add_report_to_session('backtest_manifest', run_package['manifest'], 'json')
        kpi_file = session_manager.add_report_to_session('backtest_kpi', run_package['kpi'], 'json')
        
        # Salva summary come testo
        summary_file = session_manager.add_report_to_session('backtest_summary', run_package['summary'], 'md')
        
        print(f" Backtest artefatti salvati nella sessione")
        
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


def run_all_backtests(recent_days=365):
    """Esegue backtest su tutti i preset con KPI separati per ognuno"""
    
    # Ordine deterministico (full storico + rolling + periodi critici)
    preset_order = ['full', 'recent', 'gfc', 'eurocrisis', 'covid', 'inflation2022']
    preset_order = [p for p in preset_order if p in PRESET_PERIODS]

    # Timestamp unico per questa run --all
    batch_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    results = []
    any_failed = False

    for preset in preset_order:
        print("\n" + "=" * 60)
        print(f"ALL MODE - preset={preset}")
        print("=" * 60)
        
        # Run ID distinto per ogni preset
        run_id = f"backtest_{preset}_{batch_ts}"
        
        ok = backtest_runner(preset=preset, recent_days=recent_days, run_id_override=run_id)
        results.append((preset, ok))
        any_failed = any_failed or (not ok)
        
        # Delay tra preset per evitare file lock su Windows
        if preset != preset_order[-1]:
            print(f"\n⏳ Pausa 2s prima del prossimo preset...")
            import time
            time.sleep(2)

    print("\n" + "=" * 60)
    print("ALL MODE - SUMMARY")
    print("=" * 60)
    for preset, ok in results:
        status = '✅ PASS' if ok else '❌ FAIL'
        print(f"{preset}: {status}")
    
    print(f"\nBatch timestamp: {batch_ts}")
    print(f"Tutti i report salvati in data/reports/sessions/ con suffisso _{batch_ts}")

    return not any_failed

def sanity_check(conn):
    """Controllo di integrità bloccante"""
    
    try:
        # 1. Posizioni negative (solo record backtest)
        negative_positions = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT symbol, SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL') AND run_type = 'BACKTEST'
            GROUP BY symbol
            HAVING net_qty < 0
        )
        """).fetchone()[0]
        
        if negative_positions > 0:
            print(f" Posizioni negative trovate: {negative_positions}")
            return False
        
        # 2. Cash negativo (solo record backtest)
        cash_balance = conn.execute("""
        SELECT COALESCE(SUM(CASE 
            WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
            WHEN type = 'BUY' THEN -(qty * price + fees)
            WHEN type = 'INTEREST' THEN qty
            ELSE 0 
        END), 0) as cash_balance
        FROM fiscal_ledger
        WHERE run_type = 'BACKTEST'
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
    parser = argparse.ArgumentParser(description='Backtest Runner ETF Italia Project')
    parser.add_argument('--start-date', type=str, default=None, help='Data inizio (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None, help='Data fine (YYYY-MM-DD)')
    parser.add_argument('--preset', type=str, default=None, help=f"Preset periodo: {list(PRESET_PERIODS.keys())}")
    parser.add_argument('--all', action='store_true', help='Esegui tutti i preset backtest (full + recent + periodi critici)')
    parser.add_argument('--recent-days', type=int, default=365, help='Finestra giorni per preset recent (rolling)')
    args = parser.parse_args()

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)

    if args.all:
        success = run_all_backtests(recent_days=args.recent_days)
    else:
        if args.preset and args.preset not in PRESET_PERIODS:
            raise SystemExit(f"Preset non valido: {args.preset}. Validi: {list(PRESET_PERIODS.keys())}")

        success = backtest_runner(start_date=start_date, end_date=end_date, preset=args.preset, recent_days=args.recent_days)
    if success:
        print("\n✅ Backtest completato con successo")
    else:
        print("\n❌ Backtest fallito")
        print("X Backtest runner fallito - sequenza interrotta")
        sys.exit(1)
