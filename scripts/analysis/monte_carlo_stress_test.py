"""
Stress Test Monte Carlo (DIPF §9.3)
Gate finale per validazione rischio coda prima di aumentare AUM reale.

Implementa shuffle test semplice (1000 iterazioni) per validare:
- 5th percentile MaxDD < 25% (retail risk tolerance)
- Distribuzione CAGR sotto permutazioni casuali
- Worst-case scenarios e tail risk

Conformità: DIPF §9.3, retail-grade risk assessment
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import duckdb
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
from decimal import Decimal

from utils.path_manager import get_db_path, get_path_manager
import sys
sys.path.append(str(Path(__file__).parent.parent))
from orchestration.session_manager import get_session_manager


class MonteCarloStressTest:
    """
    Monte Carlo stress test per validazione rischio coda.
    
    Implementa shuffle test semplice con 1000 iterazioni per:
    - Validare 5th percentile MaxDD < 25%
    - Analizzare distribuzione CAGR
    - Identificare worst-case scenarios
    """
    
    def __init__(self, db_path: Optional[str] = None, n_simulations: int = 1000):
        """
        Inizializza stress test.
        
        Args:
            db_path: Path al database (default: get_db_path())
            n_simulations: Numero simulazioni Monte Carlo (default: 1000)
        """
        self.db_path = db_path or get_db_path()
        self.n_simulations = n_simulations
        self.conn = None
        self.results = []
        
    def connect(self):
        """Connessione al database."""
        if self.conn is None:
            self.conn = duckdb.connect(self.db_path, read_only=True)
            
    def disconnect(self):
        """Disconnessione dal database."""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def extract_returns_from_ledger(
        self, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Estrae returns giornalieri dal fiscal_ledger.
        
        Args:
            start_date: Data inizio (YYYY-MM-DD, opzionale)
            end_date: Data fine (YYYY-MM-DD, opzionale)
            
        Returns:
            DataFrame con colonne: date, daily_return, equity
        """
        self.connect()
        
        # Usa portfolio_overview se esiste, altrimenti calcola da fiscal_ledger
        query = """
        WITH daily_equity AS (
            SELECT 
                date,
                SUM(market_value) + MAX(cash) as total_equity
            FROM portfolio_overview
            WHERE 1=1
        """
        
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += """
            GROUP BY date
            ORDER BY date
        ),
        returns AS (
            SELECT 
                date,
                total_equity,
                LAG(total_equity) OVER (ORDER BY date) as prev_equity,
                CASE 
                    WHEN LAG(total_equity) OVER (ORDER BY date) > 0 
                    THEN (total_equity / LAG(total_equity) OVER (ORDER BY date)) - 1.0
                    ELSE 0.0
                END as daily_return
            FROM daily_equity
        )
        SELECT 
            date,
            daily_return,
            total_equity as equity
        FROM returns
        WHERE prev_equity IS NOT NULL
        ORDER BY date
        """
        
        df = self.conn.execute(query, params).df()
        return df
        
    def calculate_metrics(self, returns: np.ndarray, initial_equity: float = 10000.0) -> Dict:
        """
        Calcola metriche performance da serie di returns.
        
        Args:
            returns: Array di returns giornalieri
            initial_equity: Equity iniziale (default: 10000)
            
        Returns:
            Dict con metriche: cagr, max_dd, sharpe, sortino, calmar
        """
        if len(returns) == 0:
            return {
                'cagr': 0.0,
                'max_dd': 0.0,
                'sharpe': 0.0,
                'sortino': 0.0,
                'calmar': 0.0,
                'final_equity': initial_equity
            }
            
        # Equity curve (include initial equity point for correct drawdown)
        equity_curve = np.concatenate(
            [[initial_equity], initial_equity * np.cumprod(1 + returns)]
        )
        final_equity = equity_curve[-1]
        
        # CAGR
        n_days = len(returns)
        years = n_days / 252.0
        cagr = (final_equity / initial_equity) ** (1 / years) - 1.0 if years > 0 else 0.0
        
        # Max Drawdown
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        max_dd = abs(drawdown.min())
        
        # Sharpe Ratio (annualized, risk-free = 0)
        mean_return = returns.mean()
        std_return = returns.std()
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
        
        # Sortino Ratio (annualized, downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else std_return
        sortino = (mean_return / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0
        
        # Calmar Ratio (CAGR / MaxDD)
        calmar = cagr / max_dd if max_dd > 0 else 0.0
        
        return {
            'cagr': float(cagr),
            'max_dd': float(max_dd),
            'sharpe': float(sharpe),
            'sortino': float(sortino),
            'calmar': float(calmar),
            'final_equity': float(final_equity)
        }
        
    def run_shuffle_test(
        self, 
        returns: np.ndarray,
        initial_equity: float = 10000.0,
        seed: Optional[int] = 42
    ) -> List[Dict]:
        """
        Esegue shuffle test Monte Carlo.
        
        Args:
            returns: Array di returns giornalieri
            initial_equity: Equity iniziale
            seed: Random seed per riproducibilità
            
        Returns:
            Lista di dict con metriche per ogni simulazione
        """
        if seed is not None:
            np.random.seed(seed)
            
        results = []
        
        print(f"\n{'='*60}")
        print(f"MONTE CARLO SHUFFLE TEST - {self.n_simulations} simulazioni")
        print(f"{'='*60}")
        print(f"Returns originali: {len(returns)} giorni")
        print(f"Initial equity: €{initial_equity:,.2f}")
        
        # Baseline (returns originali)
        baseline_metrics = self.calculate_metrics(returns, initial_equity)
        print(f"\nBASELINE (sequenza originale):")
        print(f"  CAGR: {baseline_metrics['cagr']*100:.2f}%")
        print(f"  MaxDD: {baseline_metrics['max_dd']*100:.2f}%")
        print(f"  Sharpe: {baseline_metrics['sharpe']:.2f}")
        print(f"  Calmar: {baseline_metrics['calmar']:.2f}")
        
        # Simulazioni shuffle
        print(f"\nEsecuzione {self.n_simulations} simulazioni shuffle...")
        for i in range(self.n_simulations):
            if (i + 1) % 100 == 0:
                print(f"  Simulazione {i+1}/{self.n_simulations}...")
                
            # Shuffle returns
            shuffled_returns = np.random.permutation(returns)
            
            # Calcola metriche
            metrics = self.calculate_metrics(shuffled_returns, initial_equity)
            metrics['simulation_id'] = i + 1
            results.append(metrics)
            
        self.results = results
        return results
        
    def analyze_results(self) -> Dict:
        """
        Analizza risultati Monte Carlo e valida gate criteria.
        
        Returns:
            Dict con statistiche e gate pass/fail
        """
        if not self.results:
            raise ValueError("Nessun risultato disponibile. Eseguire run_shuffle_test() prima.")
            
        # Estrai metriche
        cagr_values = [r['cagr'] for r in self.results]
        max_dd_values = [r['max_dd'] for r in self.results]
        sharpe_values = [r['sharpe'] for r in self.results]
        calmar_values = [r['calmar'] for r in self.results]
        
        # Percentili
        cagr_percentiles = {
            '5th': np.percentile(cagr_values, 5),
            '25th': np.percentile(cagr_values, 25),
            '50th': np.percentile(cagr_values, 50),
            '75th': np.percentile(cagr_values, 75),
            '95th': np.percentile(cagr_values, 95)
        }
        
        max_dd_percentiles = {
            '5th': np.percentile(max_dd_values, 5),
            '25th': np.percentile(max_dd_values, 25),
            '50th': np.percentile(max_dd_values, 50),
            '75th': np.percentile(max_dd_values, 75),
            '95th': np.percentile(max_dd_values, 95)
        }
        
        # Gate criteria (DIPF §9.3)
        max_dd_5pct = max_dd_percentiles['5th']
        gate_threshold = 0.25  # 25% MaxDD threshold
        gate_passed = max_dd_5pct < gate_threshold
        
        # Worst case scenario
        worst_idx = np.argmax(max_dd_values)
        worst_case = self.results[worst_idx]
        
        # Best case scenario
        best_idx = np.argmin(max_dd_values)
        best_case = self.results[best_idx]
        
        analysis = {
            'n_simulations': self.n_simulations,
            'cagr': {
                'mean': float(np.mean(cagr_values)),
                'std': float(np.std(cagr_values)),
                'min': float(np.min(cagr_values)),
                'max': float(np.max(cagr_values)),
                'percentiles': {k: float(v) for k, v in cagr_percentiles.items()}
            },
            'max_dd': {
                'mean': float(np.mean(max_dd_values)),
                'std': float(np.std(max_dd_values)),
                'min': float(np.min(max_dd_values)),
                'max': float(np.max(max_dd_values)),
                'percentiles': {k: float(v) for k, v in max_dd_percentiles.items()}
            },
            'sharpe': {
                'mean': float(np.mean(sharpe_values)),
                'std': float(np.std(sharpe_values))
            },
            'calmar': {
                'mean': float(np.mean(calmar_values)),
                'std': float(np.std(calmar_values))
            },
            'gate_criteria': {
                'max_dd_5pct': float(max_dd_5pct),
                'threshold': float(gate_threshold),
                'passed': bool(gate_passed),
                'margin': float(gate_threshold - max_dd_5pct)
            },
            'worst_case': worst_case,
            'best_case': best_case
        }
        
        return analysis
        
    def print_analysis(self, analysis: Dict):
        """
        Stampa analisi risultati in formato leggibile.
        
        Args:
            analysis: Dict da analyze_results()
        """
        print(f"\n{'='*60}")
        print(f"ANALISI RISULTATI MONTE CARLO")
        print(f"{'='*60}")
        
        print(f"\nCAGR Distribution ({analysis['n_simulations']} simulazioni):")
        print(f"  Mean: {analysis['cagr']['mean']*100:.2f}%")
        print(f"  Std:  {analysis['cagr']['std']*100:.2f}%")
        print(f"  Min:  {analysis['cagr']['min']*100:.2f}%")
        print(f"  Max:  {analysis['cagr']['max']*100:.2f}%")
        print(f"  Percentiles:")
        for pct, val in analysis['cagr']['percentiles'].items():
            print(f"    {pct}: {val*100:.2f}%")
            
        print(f"\nMaxDD Distribution:")
        print(f"  Mean: {analysis['max_dd']['mean']*100:.2f}%")
        print(f"  Std:  {analysis['max_dd']['std']*100:.2f}%")
        print(f"  Min:  {analysis['max_dd']['min']*100:.2f}%")
        print(f"  Max:  {analysis['max_dd']['max']*100:.2f}%")
        print(f"  Percentiles:")
        for pct, val in analysis['max_dd']['percentiles'].items():
            print(f"    {pct}: {val*100:.2f}%")
            
        print(f"\nSharpe Ratio:")
        print(f"  Mean: {analysis['sharpe']['mean']:.2f}")
        print(f"  Std:  {analysis['sharpe']['std']:.2f}")
        
        print(f"\nCalmar Ratio:")
        print(f"  Mean: {analysis['calmar']['mean']:.2f}")
        print(f"  Std:  {analysis['calmar']['std']:.2f}")
        
        print(f"\n{'='*60}")
        print(f"GATE CRITERIA (DIPF §9.3)")
        print(f"{'='*60}")
        gate = analysis['gate_criteria']
        print(f"5th Percentile MaxDD: {gate['max_dd_5pct']*100:.2f}%")
        print(f"Threshold (retail):   {gate['threshold']*100:.2f}%")
        print(f"Margin:               {gate['margin']*100:.2f}%")
        
        if gate['passed']:
            print(f"\n✅ GATE PASSED - Strategia adatta per retail risk tolerance")
        else:
            print(f"\n❌ GATE FAILED - Strategia troppo volatile per retail")
            print(f"   Ridurre risk_scalar o aumentare cash reserve")
            
        print(f"\n{'='*60}")
        print(f"WORST CASE SCENARIO (Simulation #{analysis['worst_case']['simulation_id']})")
        print(f"{'='*60}")
        wc = analysis['worst_case']
        print(f"  CAGR:   {wc['cagr']*100:.2f}%")
        print(f"  MaxDD:  {wc['max_dd']*100:.2f}%")
        print(f"  Sharpe: {wc['sharpe']:.2f}")
        print(f"  Calmar: {wc['calmar']:.2f}")
        
        print(f"\n{'='*60}")
        print(f"BEST CASE SCENARIO (Simulation #{analysis['best_case']['simulation_id']})")
        print(f"{'='*60}")
        bc = analysis['best_case']
        print(f"  CAGR:   {bc['cagr']*100:.2f}%")
        print(f"  MaxDD:  {bc['max_dd']*100:.2f}%")
        print(f"  Sharpe: {bc['sharpe']:.2f}")
        print(f"  Calmar: {bc['calmar']:.2f}")
        
    def save_report(
        self, 
        analysis: Dict,
        baseline_metrics: Dict,
        output_dir: Optional[str] = None,
        use_session: bool = True
    ):
        """
        Salva report stress test in JSON e Markdown.
        
        Args:
            analysis: Dict da analyze_results()
            baseline_metrics: Metriche baseline (sequenza originale)
            output_dir: Directory output (default: usa session manager)
            use_session: Se True usa session manager (default), altrimenti path diretto
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if use_session and output_dir is None:
            # Usa session manager per struttura corretta
            sm = get_session_manager(script_name='stress_test_monte_carlo')
            output_dir = sm.get_subdir_path('stress_tests')
        elif output_dir is None:
            # Fallback: path diretto (legacy)
            pm = get_path_manager()
            output_dir = pm.root / 'data' / 'reports' / 'stress_test'
        else:
            output_dir = Path(output_dir)
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON report
        report_data = {
            'timestamp': timestamp,
            'test_type': 'monte_carlo_shuffle',
            'n_simulations': self.n_simulations,
            'baseline': baseline_metrics,
            'analysis': analysis
        }
        
        json_path = output_dir / f"monte_carlo_stress_test_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)
            
        print(f"\n✅ Report JSON salvato: {json_path}")
        
        # Markdown report
        md_path = output_dir / f"monte_carlo_stress_test_{timestamp}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Stress Test Monte Carlo - {timestamp}\n\n")
            f.write(f"**Test Type:** Monte Carlo Shuffle Test\n")
            f.write(f"**Simulazioni:** {self.n_simulations}\n")
            f.write(f"**Conformità:** DIPF §9.3\n\n")
            
            f.write(f"## Baseline (Sequenza Originale)\n\n")
            f.write(f"| Metrica | Valore |\n")
            f.write(f"|---------|--------|\n")
            f.write(f"| CAGR | {baseline_metrics['cagr']*100:.2f}% |\n")
            f.write(f"| MaxDD | {baseline_metrics['max_dd']*100:.2f}% |\n")
            f.write(f"| Sharpe | {baseline_metrics['sharpe']:.2f} |\n")
            f.write(f"| Sortino | {baseline_metrics['sortino']:.2f} |\n")
            f.write(f"| Calmar | {baseline_metrics['calmar']:.2f} |\n\n")
            
            f.write(f"## Distribuzione CAGR\n\n")
            f.write(f"| Statistica | Valore |\n")
            f.write(f"|------------|--------|\n")
            f.write(f"| Mean | {analysis['cagr']['mean']*100:.2f}% |\n")
            f.write(f"| Std | {analysis['cagr']['std']*100:.2f}% |\n")
            f.write(f"| Min | {analysis['cagr']['min']*100:.2f}% |\n")
            f.write(f"| Max | {analysis['cagr']['max']*100:.2f}% |\n")
            f.write(f"| 5th Percentile | {analysis['cagr']['percentiles']['5th']*100:.2f}% |\n")
            f.write(f"| 25th Percentile | {analysis['cagr']['percentiles']['25th']*100:.2f}% |\n")
            f.write(f"| Median | {analysis['cagr']['percentiles']['50th']*100:.2f}% |\n")
            f.write(f"| 75th Percentile | {analysis['cagr']['percentiles']['75th']*100:.2f}% |\n")
            f.write(f"| 95th Percentile | {analysis['cagr']['percentiles']['95th']*100:.2f}% |\n\n")
            
            f.write(f"## Distribuzione MaxDD\n\n")
            f.write(f"| Statistica | Valore |\n")
            f.write(f"|------------|--------|\n")
            f.write(f"| Mean | {analysis['max_dd']['mean']*100:.2f}% |\n")
            f.write(f"| Std | {analysis['max_dd']['std']*100:.2f}% |\n")
            f.write(f"| Min | {analysis['max_dd']['min']*100:.2f}% |\n")
            f.write(f"| Max | {analysis['max_dd']['max']*100:.2f}% |\n")
            f.write(f"| 5th Percentile | {analysis['max_dd']['percentiles']['5th']*100:.2f}% |\n")
            f.write(f"| 25th Percentile | {analysis['max_dd']['percentiles']['25th']*100:.2f}% |\n")
            f.write(f"| Median | {analysis['max_dd']['percentiles']['50th']*100:.2f}% |\n")
            f.write(f"| 75th Percentile | {analysis['max_dd']['percentiles']['75th']*100:.2f}% |\n")
            f.write(f"| 95th Percentile | {analysis['max_dd']['percentiles']['95th']*100:.2f}% |\n\n")
            
            f.write(f"## Gate Criteria (DIPF §9.3)\n\n")
            gate = analysis['gate_criteria']
            f.write(f"| Criterio | Valore |\n")
            f.write(f"|----------|--------|\n")
            f.write(f"| 5th Percentile MaxDD | {gate['max_dd_5pct']*100:.2f}% |\n")
            f.write(f"| Threshold (retail) | {gate['threshold']*100:.2f}% |\n")
            f.write(f"| Margin | {gate['margin']*100:.2f}% |\n")
            f.write(f"| **Status** | **{'✅ PASSED' if gate['passed'] else '❌ FAILED'}** |\n\n")
            
            if gate['passed']:
                f.write(f"**Conclusione:** Strategia adatta per retail risk tolerance.\n\n")
            else:
                f.write(f"**Conclusione:** Strategia troppo volatile per retail. ")
                f.write(f"Ridurre risk_scalar o aumentare cash reserve.\n\n")
                
            f.write(f"## Worst Case Scenario\n\n")
            wc = analysis['worst_case']
            f.write(f"**Simulation ID:** {wc['simulation_id']}\n\n")
            f.write(f"| Metrica | Valore |\n")
            f.write(f"|---------|--------|\n")
            f.write(f"| CAGR | {wc['cagr']*100:.2f}% |\n")
            f.write(f"| MaxDD | {wc['max_dd']*100:.2f}% |\n")
            f.write(f"| Sharpe | {wc['sharpe']:.2f} |\n")
            f.write(f"| Calmar | {wc['calmar']:.2f} |\n\n")
            
            f.write(f"## Best Case Scenario\n\n")
            bc = analysis['best_case']
            f.write(f"**Simulation ID:** {bc['simulation_id']}\n\n")
            f.write(f"| Metrica | Valore |\n")
            f.write(f"|---------|--------|\n")
            f.write(f"| CAGR | {bc['cagr']*100:.2f}% |\n")
            f.write(f"| MaxDD | {bc['max_dd']*100:.2f}% |\n")
            f.write(f"| Sharpe | {bc['sharpe']:.2f} |\n")
            f.write(f"| Calmar | {bc['calmar']:.2f} |\n\n")
            
        print(f"✅ Report Markdown salvato: {md_path}")
        
        return json_path, md_path


def main():
    """
    Main entry point per stress test Monte Carlo.
    
    Usage:
        python stress_test_monte_carlo.py [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--n-sims N]
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Stress Test Monte Carlo (DIPF §9.3) - Gate finale pre-AUM"
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Data inizio analisi (YYYY-MM-DD, opzionale)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='Data fine analisi (YYYY-MM-DD, opzionale)'
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
    
    print(f"\n{'='*60}")
    print(f"STRESS TEST MONTE CARLO - GATE FINALE PRE-AUM")
    print(f"{'='*60}")
    print(f"Conformità: DIPF §9.3")
    print(f"Simulazioni: {args.n_sims}")
    print(f"Random seed: {args.seed}")
    
    # Inizializza stress test
    stress_test = MonteCarloStressTest(n_simulations=args.n_sims)
    
    try:
        # Estrai returns da ledger
        print(f"\nEstrazione returns da fiscal_ledger...")
        df_returns = stress_test.extract_returns_from_ledger(
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        if len(df_returns) == 0:
            print("❌ ERRORE: Nessun dato disponibile nel ledger")
            sys.exit(1)
            
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
            seed=args.seed
        )
        
        # Analizza risultati
        analysis = stress_test.analyze_results()
        
        # Stampa analisi
        stress_test.print_analysis(analysis)
        
        # Salva report
        json_path, md_path = stress_test.save_report(analysis, baseline_metrics)
        
        # Exit code basato su gate
        if analysis['gate_criteria']['passed']:
            print(f"\n{'='*60}")
            print(f"✅ GATE FINALE SUPERATO")
            print(f"{'='*60}")
            print(f"Sistema pronto per aumento AUM reale.")
            print(f"5th percentile MaxDD: {analysis['gate_criteria']['max_dd_5pct']*100:.2f}% < 25%")
            sys.exit(0)
        else:
            print(f"\n{'='*60}")
            print(f"❌ GATE FINALE FALLITO")
            print(f"{'='*60}")
            print(f"Sistema NON pronto per aumento AUM reale.")
            print(f"5th percentile MaxDD: {analysis['gate_criteria']['max_dd_5pct']*100:.2f}% >= 25%")
            print(f"\nAzioni consigliate:")
            print(f"  1. Ridurre risk_scalar globale")
            print(f"  2. Aumentare cash_reserve_pct")
            print(f"  3. Ridurre max_positions")
            print(f"  4. Aumentare stop-loss threshold")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ ERRORE durante stress test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        stress_test.disconnect()


if __name__ == '__main__':
    main()
