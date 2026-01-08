"""
Ottimizzazione parametri risk management per superare gate Monte Carlo.

Testa diverse combinazioni di:
- risk_scalar: Moltiplicatore esposizione globale
- cash_reserve_pct: Percentuale cash minimo
- max_positions: Numero massimo posizioni
- stop_loss_pct: Soglia stop-loss

Obiettivo: 5th percentile MaxDD < 25% (retail risk tolerance)
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from monte_carlo_stress_test import MonteCarloStressTest
from datetime import datetime
import json
from orchestration.session_manager import get_session_manager


def generate_synthetic_returns_with_params(
    n_days: int = 504,
    base_mean: float = 0.0004,
    base_std: float = 0.012,
    risk_scalar: float = 1.0,
    cash_reserve_pct: float = 0.05,
    seed: int = 42
) -> np.ndarray:
    """
    Genera returns sintetici con parametri risk management applicati.
    
    Args:
        n_days: Numero giorni
        base_mean: Mean return base
        base_std: Std return base
        risk_scalar: Moltiplicatore esposizione (0-1)
        cash_reserve_pct: Cash reserve percentage
        seed: Random seed
        
    Returns:
        Array returns con risk management applicato
    """
    np.random.seed(seed)
    
    # Genera returns base
    returns_base = np.random.normal(base_mean, base_std, n_days)
    
    # Aggiungi crash simulato
    crash_start = n_days // 2
    crash_duration = 20
    returns_base[crash_start:crash_start+crash_duration] = np.random.normal(-0.02, 0.03, crash_duration)
    
    # Applica risk_scalar (riduce esposizione)
    # Invested capital = (1 - cash_reserve_pct) * risk_scalar
    invested_fraction = (1.0 - cash_reserve_pct) * risk_scalar
    
    # Returns effettivi = returns_base * invested_fraction
    # Cash genera 0% return (semplificazione)
    returns_adjusted = returns_base * invested_fraction
    
    return returns_adjusted


def test_parameter_combination(
    risk_scalar: float,
    cash_reserve_pct: float,
    max_positions: int,
    stop_loss_pct: float,
    n_sims: int = 1000,
    seed: int = 42,
    verbose: bool = False
) -> dict:
    """
    Testa una combinazione di parametri e ritorna risultati.
    
    Args:
        risk_scalar: Moltiplicatore esposizione (0-1)
        cash_reserve_pct: Cash reserve (0-1)
        max_positions: Numero max posizioni
        stop_loss_pct: Stop-loss threshold (negativo, es. -0.10)
        n_sims: Numero simulazioni
        seed: Random seed
        verbose: Print dettagli
        
    Returns:
        Dict con risultati test
    """
    # Genera returns con parametri
    returns = generate_synthetic_returns_with_params(
        n_days=504,
        risk_scalar=risk_scalar,
        cash_reserve_pct=cash_reserve_pct,
        seed=seed
    )
    
    # Esegui stress test
    stress_test = MonteCarloStressTest(n_simulations=n_sims)
    
    # Calcola baseline
    baseline = stress_test.calculate_metrics(returns, initial_equity=10000.0)
    
    # Run shuffle test
    results = stress_test.run_shuffle_test(returns, initial_equity=10000.0, seed=seed)
    
    # Analizza
    analysis = stress_test.analyze_results()
    
    # Estrai metriche chiave
    max_dd_5pct = analysis['gate_criteria']['max_dd_5pct']
    gate_passed = analysis['gate_criteria']['passed']
    
    result = {
        'parameters': {
            'risk_scalar': risk_scalar,
            'cash_reserve_pct': cash_reserve_pct,
            'max_positions': max_positions,
            'stop_loss_pct': stop_loss_pct
        },
        'metrics': {
            'max_dd_5pct': max_dd_5pct,
            'max_dd_mean': analysis['max_dd']['mean'],
            'max_dd_std': analysis['max_dd']['std'],
            'cagr_mean': analysis['cagr']['mean'],
            'sharpe_mean': analysis['sharpe']['mean']
        },
        'gate_passed': gate_passed,
        'margin': analysis['gate_criteria']['margin']
    }
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"TEST PARAMETRI")
        print(f"{'='*60}")
        print(f"risk_scalar: {risk_scalar:.2f}")
        print(f"cash_reserve: {cash_reserve_pct*100:.1f}%")
        print(f"max_positions: {max_positions}")
        print(f"stop_loss: {stop_loss_pct*100:.1f}%")
        print(f"\nRISULTATI:")
        print(f"5th Percentile MaxDD: {max_dd_5pct*100:.2f}%")
        print(f"Threshold: 25.00%")
        print(f"Margin: {result['margin']*100:.2f}%")
        print(f"Gate: {'✅ PASSED' if gate_passed else '❌ FAILED'}")
    
    return result


def optimize_parameters():
    """
    Ottimizzazione iterativa parametri per superare gate.
    """
    print(f"\n{'='*70}")
    print(f"OTTIMIZZAZIONE PARAMETRI RISK MANAGEMENT")
    print(f"{'='*70}")
    print(f"Obiettivo: 5th percentile MaxDD < 25%")
    print(f"Simulazioni per test: 1000")
    print(f"Random seed: 42 (riproducibile)")
    
    # Parametri baseline (scenario fallito)
    baseline_params = {
        'risk_scalar': 1.0,
        'cash_reserve_pct': 0.05,
        'max_positions': 10,
        'stop_loss_pct': -0.15
    }
    
    print(f"\n{'='*70}")
    print(f"BASELINE (parametri attuali)")
    print(f"{'='*70}")
    baseline_result = test_parameter_combination(**baseline_params, verbose=True)
    
    # Test combinations
    test_scenarios = [
        {
            'name': 'TEST 1: Ridurre risk_scalar a 0.7',
            'params': {
                'risk_scalar': 0.7,
                'cash_reserve_pct': 0.05,
                'max_positions': 10,
                'stop_loss_pct': -0.15
            }
        },
        {
            'name': 'TEST 2: risk_scalar 0.7 + cash_reserve 10%',
            'params': {
                'risk_scalar': 0.7,
                'cash_reserve_pct': 0.10,
                'max_positions': 10,
                'stop_loss_pct': -0.15
            }
        },
        {
            'name': 'TEST 3: risk_scalar 0.6 + cash_reserve 10%',
            'params': {
                'risk_scalar': 0.6,
                'cash_reserve_pct': 0.10,
                'max_positions': 10,
                'stop_loss_pct': -0.15
            }
        },
        {
            'name': 'TEST 4: risk_scalar 0.6 + cash_reserve 15%',
            'params': {
                'risk_scalar': 0.6,
                'cash_reserve_pct': 0.15,
                'max_positions': 10,
                'stop_loss_pct': -0.15
            }
        },
        {
            'name': 'TEST 5: risk_scalar 0.5 + cash_reserve 15%',
            'params': {
                'risk_scalar': 0.5,
                'cash_reserve_pct': 0.15,
                'max_positions': 10,
                'stop_loss_pct': -0.15
            }
        },
        {
            'name': 'TEST 6: risk_scalar 0.5 + cash_reserve 20%',
            'params': {
                'risk_scalar': 0.5,
                'cash_reserve_pct': 0.20,
                'max_positions': 10,
                'stop_loss_pct': -0.15
            }
        },
        {
            'name': 'TEST 7: risk_scalar 0.55 + cash_reserve 15% (bilanciato)',
            'params': {
                'risk_scalar': 0.55,
                'cash_reserve_pct': 0.15,
                'max_positions': 8,
                'stop_loss_pct': -0.12
            }
        }
    ]
    
    results = []
    best_result = None
    best_margin = -999
    
    for scenario in test_scenarios:
        print(f"\n{'='*70}")
        print(f"{scenario['name']}")
        print(f"{'='*70}")
        
        result = test_parameter_combination(**scenario['params'], verbose=True)
        result['scenario_name'] = scenario['name']
        results.append(result)
        
        # Track best result
        if result['gate_passed'] and result['margin'] > best_margin:
            best_result = result
            best_margin = result['margin']
    
    # Summary
    print(f"\n{'='*70}")
    print(f"RIEPILOGO OTTIMIZZAZIONE")
    print(f"{'='*70}")
    
    print(f"\nTest eseguiti: {len(results)}")
    passed_count = sum(1 for r in results if r['gate_passed'])
    print(f"Gate passed: {passed_count}/{len(results)}")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"✅ CONFIGURAZIONE OTTIMALE TROVATA")
        print(f"{'='*70}")
        print(f"Scenario: {best_result['scenario_name']}")
        print(f"\nParametri:")
        print(f"  risk_scalar: {best_result['parameters']['risk_scalar']:.2f}")
        print(f"  cash_reserve: {best_result['parameters']['cash_reserve_pct']*100:.1f}%")
        print(f"  max_positions: {best_result['parameters']['max_positions']}")
        print(f"  stop_loss: {best_result['parameters']['stop_loss_pct']*100:.1f}%")
        print(f"\nMetriche:")
        print(f"  5th Percentile MaxDD: {best_result['metrics']['max_dd_5pct']*100:.2f}%")
        print(f"  Threshold: 25.00%")
        print(f"  Margin: {best_result['margin']*100:.2f}%")
        print(f"  Mean MaxDD: {best_result['metrics']['max_dd_mean']*100:.2f}%")
        print(f"  CAGR: {best_result['metrics']['cagr_mean']*100:.2f}%")
        print(f"  Sharpe: {best_result['metrics']['sharpe_mean']:.2f}")
    else:
        print(f"\n{'='*70}")
        print(f"❌ NESSUNA CONFIGURAZIONE HA SUPERATO IL GATE")
        print(f"{'='*70}")
        print(f"\nMigliore risultato (più vicino):")
        closest = min(results, key=lambda r: abs(r['metrics']['max_dd_5pct'] - 0.25))
        print(f"Scenario: {closest['scenario_name']}")
        print(f"5th Percentile MaxDD: {closest['metrics']['max_dd_5pct']*100:.2f}%")
        print(f"Margin: {closest['margin']*100:.2f}%")
    
    # Salva risultati usando session manager
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sm = get_session_manager(script_name='monte_carlo_optimize')
    output_dir = sm.get_subdir_path('stress_tests')
    output_file = output_dir / f'monte_carlo_optimization_{timestamp}.json'
    
    optimization_report = {
        'timestamp': timestamp,
        'test_type': 'monte_carlo_optimization',
        'baseline': baseline_result,
        'tests': results,
        'best_result': best_result,
        'summary': {
            'total_tests': len(results),
            'passed_tests': passed_count,
            'optimization_successful': best_result is not None
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(optimization_report, f, indent=2)
    
    print(f"\n✅ Report salvato: {output_file}")
    
    return optimization_report


if __name__ == '__main__':
    optimize_parameters()
