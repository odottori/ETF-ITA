"""
Script di esempio per eseguire stress test Monte Carlo.

Questo script può essere eseguito in due modalità:
1. Con dati reali dal fiscal_ledger (se disponibili)
2. Con dati sintetici per validazione implementazione

Usage:
    # Con dati reali
    python run_stress_test_example.py --mode real --start-date 2023-01-01
    
    # Con dati sintetici
    python run_stress_test_example.py --mode synthetic --n-days 504
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from monte_carlo_stress_test import MonteCarloStressTest


def generate_synthetic_returns(n_days: int = 504, seed: int = 42) -> np.ndarray:
    """
    Genera returns sintetici realistici per test.
    
    Args:
        n_days: Numero giorni (default: 504 = ~2 anni trading)
        seed: Random seed
        
    Returns:
        Array di returns giornalieri
    """
    np.random.seed(seed)
    
    # Parametri realistici per strategia trend-following retail
    # Mean: 0.04% daily (~10% annualized)
    # Std: 1.2% daily (~19% annualized vol)
    mean_daily = 0.0004
    std_daily = 0.012
    
    # Genera returns con distribuzione normale
    returns = np.random.normal(mean_daily, std_daily, n_days)
    
    # Aggiungi regime shift (simulazione crash)
    # Crash di 20 giorni a metà periodo
    crash_start = n_days // 2
    crash_duration = 20
    returns[crash_start:crash_start+crash_duration] = np.random.normal(-0.02, 0.03, crash_duration)
    
    return returns


def run_synthetic_test(n_days: int = 504, n_sims: int = 1000, seed: int = 42):
    """
    Esegue stress test con dati sintetici.
    
    Args:
        n_days: Numero giorni di trading
        n_sims: Numero simulazioni Monte Carlo
        seed: Random seed
    """
    print(f"\n{'='*60}")
    print(f"STRESS TEST MONTE CARLO - MODALITÀ SINTETICA")
    print(f"{'='*60}")
    print(f"Giorni trading: {n_days}")
    print(f"Simulazioni: {n_sims}")
    print(f"Random seed: {seed}")
    
    # Genera returns sintetici
    print(f"\nGenerazione returns sintetici...")
    returns = generate_synthetic_returns(n_days=n_days, seed=seed)
    
    print(f"✅ Generati {len(returns)} returns")
    print(f"   Mean daily: {returns.mean()*100:.4f}%")
    print(f"   Std daily: {returns.std()*100:.4f}%")
    print(f"   Min: {returns.min()*100:.2f}%")
    print(f"   Max: {returns.max()*100:.2f}%")
    
    # Inizializza stress test
    stress_test = MonteCarloStressTest(n_simulations=n_sims)
    
    # Calcola baseline
    initial_equity = 10000.0
    baseline_metrics = stress_test.calculate_metrics(returns, initial_equity)
    
    print(f"\nBASELINE (sequenza originale):")
    print(f"  CAGR: {baseline_metrics['cagr']*100:.2f}%")
    print(f"  MaxDD: {baseline_metrics['max_dd']*100:.2f}%")
    print(f"  Sharpe: {baseline_metrics['sharpe']:.2f}")
    print(f"  Sortino: {baseline_metrics['sortino']:.2f}")
    print(f"  Calmar: {baseline_metrics['calmar']:.2f}")
    
    # Esegui shuffle test
    results = stress_test.run_shuffle_test(
        returns=returns,
        initial_equity=initial_equity,
        seed=seed
    )
    
    # Analizza risultati
    analysis = stress_test.analyze_results()
    
    # Stampa analisi
    stress_test.print_analysis(analysis)
    
    # Salva report
    json_path, md_path = stress_test.save_report(analysis, baseline_metrics)
    
    # Conclusione
    print(f"\n{'='*60}")
    if analysis['gate_criteria']['passed']:
        print(f"✅ GATE FINALE SUPERATO")
        print(f"{'='*60}")
        print(f"Sistema pronto per aumento AUM reale.")
        print(f"5th percentile MaxDD: {analysis['gate_criteria']['max_dd_5pct']*100:.2f}% < 25%")
        return 0
    else:
        print(f"❌ GATE FINALE FALLITO")
        print(f"{'='*60}")
        print(f"Sistema NON pronto per aumento AUM reale.")
        print(f"5th percentile MaxDD: {analysis['gate_criteria']['max_dd_5pct']*100:.2f}% >= 25%")
        print(f"\nAzioni consigliate:")
        print(f"  1. Ridurre risk_scalar globale")
        print(f"  2. Aumentare cash_reserve_pct")
        print(f"  3. Ridurre max_positions")
        print(f"  4. Aumentare stop-loss threshold")
        return 1


def run_real_test(start_date: str = None, end_date: str = None, n_sims: int = 1000, seed: int = 42):
    """
    Esegue stress test con dati reali dal fiscal_ledger.
    
    Args:
        start_date: Data inizio (YYYY-MM-DD)
        end_date: Data fine (YYYY-MM-DD)
        n_sims: Numero simulazioni Monte Carlo
        seed: Random seed
    """
    print(f"\n{'='*60}")
    print(f"STRESS TEST MONTE CARLO - MODALITÀ REALE")
    print(f"{'='*60}")
    print(f"Periodo: {start_date or 'ALL'} → {end_date or 'ALL'}")
    print(f"Simulazioni: {n_sims}")
    print(f"Random seed: {seed}")
    
    # Inizializza stress test
    stress_test = MonteCarloStressTest(n_simulations=n_sims)
    
    try:
        # Estrai returns da ledger
        print(f"\nEstrazione returns da fiscal_ledger...")
        df_returns = stress_test.extract_returns_from_ledger(
            start_date=start_date,
            end_date=end_date
        )
        
        if len(df_returns) == 0:
            print("❌ ERRORE: Nessun dato disponibile nel ledger")
            print("   Suggerimento: Eseguire prima un backtest o usare modalità synthetic")
            return 1
            
        print(f"✅ Estratti {len(df_returns)} giorni di trading")
        print(f"   Periodo: {df_returns['date'].min()} → {df_returns['date'].max()}")
        
        returns = df_returns['daily_return'].values
        initial_equity = df_returns['equity'].iloc[0]
        
        # Calcola baseline
        baseline_metrics = stress_test.calculate_metrics(returns, initial_equity)
        
        # Esegui shuffle test
        results = stress_test.run_shuffle_test(
            returns=returns,
            initial_equity=initial_equity,
            seed=seed
        )
        
        # Analizza risultati
        analysis = stress_test.analyze_results()
        
        # Stampa analisi
        stress_test.print_analysis(analysis)
        
        # Salva report
        json_path, md_path = stress_test.save_report(analysis, baseline_metrics)
        
        # Conclusione
        print(f"\n{'='*60}")
        if analysis['gate_criteria']['passed']:
            print(f"✅ GATE FINALE SUPERATO")
            print(f"{'='*60}")
            print(f"Sistema pronto per aumento AUM reale.")
            print(f"5th percentile MaxDD: {analysis['gate_criteria']['max_dd_5pct']*100:.2f}% < 25%")
            return 0
        else:
            print(f"❌ GATE FINALE FALLITO")
            print(f"{'='*60}")
            print(f"Sistema NON pronto per aumento AUM reale.")
            print(f"5th percentile MaxDD: {analysis['gate_criteria']['max_dd_5pct']*100:.2f}% >= 25%")
            print(f"\nAzioni consigliate:")
            print(f"  1. Ridurre risk_scalar globale")
            print(f"  2. Aumentare cash_reserve_pct")
            print(f"  3. Ridurre max_positions")
            print(f"  4. Aumentare stop-loss threshold")
            return 1
            
    except Exception as e:
        print(f"\n❌ ERRORE durante stress test: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        stress_test.disconnect()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Stress Test Monte Carlo - Esempio esecuzione"
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['real', 'synthetic'],
        default='synthetic',
        help='Modalità: real (dati ledger) o synthetic (dati generati)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Data inizio (YYYY-MM-DD, solo per mode=real)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='Data fine (YYYY-MM-DD, solo per mode=real)'
    )
    parser.add_argument(
        '--n-days',
        type=int,
        default=504,
        help='Numero giorni (solo per mode=synthetic, default: 504)'
    )
    parser.add_argument(
        '--n-sims',
        type=int,
        default=1000,
        help='Numero simulazioni Monte Carlo (default: 1000)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed per riproducibilità (default: 42)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'synthetic':
        exit_code = run_synthetic_test(
            n_days=args.n_days,
            n_sims=args.n_sims,
            seed=args.seed
        )
    else:
        exit_code = run_real_test(
            start_date=args.start_date,
            end_date=args.end_date,
            n_sims=args.n_sims,
            seed=args.seed
        )
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
