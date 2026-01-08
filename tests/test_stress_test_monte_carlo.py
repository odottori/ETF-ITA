"""
Test suite per stress_test_monte_carlo.py
Valida implementazione Monte Carlo secondo DIPF §9.3
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil

from scripts.analysis.monte_carlo_stress_test import MonteCarloStressTest


class TestMonteCarloStressTest:
    """Test suite per MonteCarloStressTest"""
    
    @pytest.fixture
    def stress_test(self):
        """Fixture per istanza stress test"""
        return MonteCarloStressTest(n_simulations=100)  # Ridotto per test veloci
        
    @pytest.fixture
    def sample_returns(self):
        """Fixture per returns sintetici"""
        np.random.seed(42)
        # Genera returns con caratteristiche realistiche
        # Mean: 0.05% daily (~13% annualized)
        # Std: 1.0% daily (~16% annualized vol)
        returns = np.random.normal(0.0005, 0.01, 252)  # 1 anno
        return returns
        
    def test_calculate_metrics_basic(self, stress_test, sample_returns):
        """Test calcolo metriche base"""
        metrics = stress_test.calculate_metrics(sample_returns, initial_equity=10000.0)
        
        # Verifica presenza campi obbligatori
        assert 'cagr' in metrics
        assert 'max_dd' in metrics
        assert 'sharpe' in metrics
        assert 'sortino' in metrics
        assert 'calmar' in metrics
        assert 'final_equity' in metrics
        
        # Verifica tipi
        assert isinstance(metrics['cagr'], float)
        assert isinstance(metrics['max_dd'], float)
        assert isinstance(metrics['sharpe'], float)
        
        # Verifica range realistici
        assert -1.0 <= metrics['cagr'] <= 2.0  # -100% to +200%
        assert 0.0 <= metrics['max_dd'] <= 1.0  # 0% to 100%
        assert metrics['final_equity'] > 0
        
    def test_calculate_metrics_zero_returns(self, stress_test):
        """Test metriche con returns zero (flat equity)"""
        returns = np.zeros(252)
        metrics = stress_test.calculate_metrics(returns, initial_equity=10000.0)
        
        assert metrics['cagr'] == 0.0
        assert metrics['max_dd'] == 0.0
        assert metrics['final_equity'] == 10000.0
        
    def test_calculate_metrics_negative_returns(self, stress_test):
        """Test metriche con returns negativi (drawdown)"""
        # Simulazione crash: -2% daily per 20 giorni
        returns = np.full(20, -0.02)
        metrics = stress_test.calculate_metrics(returns, initial_equity=10000.0)
        
        assert metrics['cagr'] < 0
        assert metrics['max_dd'] > 0.30  # Dovrebbe essere ~33%
        assert metrics['final_equity'] < 10000.0
        
    def test_calculate_metrics_positive_returns(self, stress_test):
        """Test metriche con returns positivi (bull market)"""
        # Simulazione bull: +1% daily per 100 giorni
        returns = np.full(100, 0.01)
        metrics = stress_test.calculate_metrics(returns, initial_equity=10000.0)
        
        assert metrics['cagr'] > 0
        assert metrics['max_dd'] == 0.0  # Nessun drawdown
        assert metrics['final_equity'] > 10000.0
        
    def test_run_shuffle_test_deterministic(self, stress_test, sample_returns):
        """Test shuffle test con seed deterministico"""
        # Prima run
        results1 = stress_test.run_shuffle_test(sample_returns, seed=42)
        
        # Seconda run con stesso seed
        stress_test2 = MonteCarloStressTest(n_simulations=100)
        results2 = stress_test2.run_shuffle_test(sample_returns, seed=42)
        
        # Verifica riproducibilità
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert abs(r1['cagr'] - r2['cagr']) < 1e-10
            assert abs(r1['max_dd'] - r2['max_dd']) < 1e-10
            
    def test_run_shuffle_test_count(self, stress_test, sample_returns):
        """Test numero simulazioni corretto"""
        n_sims = 50
        stress_test_custom = MonteCarloStressTest(n_simulations=n_sims)
        results = stress_test_custom.run_shuffle_test(sample_returns, seed=42)
        
        assert len(results) == n_sims
        
    def test_run_shuffle_test_simulation_ids(self, stress_test, sample_returns):
        """Test simulation_id sequenziali"""
        results = stress_test.run_shuffle_test(sample_returns, seed=42)
        
        for i, result in enumerate(results):
            assert result['simulation_id'] == i + 1
            
    def test_analyze_results_structure(self, stress_test, sample_returns):
        """Test struttura output analyze_results"""
        stress_test.run_shuffle_test(sample_returns, seed=42)
        analysis = stress_test.analyze_results()
        
        # Verifica struttura top-level
        assert 'n_simulations' in analysis
        assert 'cagr' in analysis
        assert 'max_dd' in analysis
        assert 'sharpe' in analysis
        assert 'calmar' in analysis
        assert 'gate_criteria' in analysis
        assert 'worst_case' in analysis
        assert 'best_case' in analysis
        
        # Verifica struttura CAGR
        assert 'mean' in analysis['cagr']
        assert 'std' in analysis['cagr']
        assert 'min' in analysis['cagr']
        assert 'max' in analysis['cagr']
        assert 'percentiles' in analysis['cagr']
        
        # Verifica percentili
        percentiles = analysis['cagr']['percentiles']
        assert '5th' in percentiles
        assert '25th' in percentiles
        assert '50th' in percentiles
        assert '75th' in percentiles
        assert '95th' in percentiles
        
    def test_analyze_results_gate_criteria(self, stress_test, sample_returns):
        """Test gate criteria (DIPF §9.3)"""
        stress_test.run_shuffle_test(sample_returns, seed=42)
        analysis = stress_test.analyze_results()
        
        gate = analysis['gate_criteria']
        
        # Verifica campi obbligatori
        assert 'max_dd_5pct' in gate
        assert 'threshold' in gate
        assert 'passed' in gate
        assert 'margin' in gate
        
        # Verifica threshold corretto (25% per retail)
        assert gate['threshold'] == 0.25
        
        # Verifica logica passed
        if gate['max_dd_5pct'] < gate['threshold']:
            assert gate['passed'] is True
        else:
            assert gate['passed'] is False
            
        # Verifica margin
        expected_margin = gate['threshold'] - gate['max_dd_5pct']
        assert abs(gate['margin'] - expected_margin) < 1e-10
        
    def test_analyze_results_worst_best_case(self, stress_test, sample_returns):
        """Test worst/best case scenarios"""
        stress_test.run_shuffle_test(sample_returns, seed=42)
        analysis = stress_test.analyze_results()
        
        worst = analysis['worst_case']
        best = analysis['best_case']
        
        # Verifica worst case ha MaxDD massimo
        all_max_dd = [r['max_dd'] for r in stress_test.results]
        assert worst['max_dd'] == max(all_max_dd)
        
        # Verifica best case ha MaxDD minimo
        assert best['max_dd'] == min(all_max_dd)
        
        # Verifica worst case peggiore di best case
        assert worst['max_dd'] >= best['max_dd']
        
    def test_analyze_results_percentile_ordering(self, stress_test, sample_returns):
        """Test ordinamento percentili"""
        stress_test.run_shuffle_test(sample_returns, seed=42)
        analysis = stress_test.analyze_results()
        
        # Verifica ordinamento percentili MaxDD
        pct = analysis['max_dd']['percentiles']
        assert pct['5th'] <= pct['25th']
        assert pct['25th'] <= pct['50th']
        assert pct['50th'] <= pct['75th']
        assert pct['75th'] <= pct['95th']
        
    def test_save_report_creates_files(self, stress_test, sample_returns):
        """Test creazione file report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            stress_test.run_shuffle_test(sample_returns, seed=42)
            analysis = stress_test.analyze_results()
            baseline = stress_test.calculate_metrics(sample_returns)
            
            json_path, md_path = stress_test.save_report(
                analysis, 
                baseline,
                output_dir=tmpdir
            )
            
            # Verifica file esistono
            assert Path(json_path).exists()
            assert Path(md_path).exists()
            
            # Verifica estensioni
            assert json_path.suffix == '.json'
            assert md_path.suffix == '.md'
            
    def test_save_report_json_structure(self, stress_test, sample_returns):
        """Test struttura JSON report"""
        import json
        
        with tempfile.TemporaryDirectory() as tmpdir:
            stress_test.run_shuffle_test(sample_returns, seed=42)
            analysis = stress_test.analyze_results()
            baseline = stress_test.calculate_metrics(sample_returns)
            
            json_path, _ = stress_test.save_report(
                analysis, 
                baseline,
                output_dir=tmpdir
            )
            
            # Leggi e valida JSON
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            assert 'timestamp' in data
            assert 'test_type' in data
            assert 'n_simulations' in data
            assert 'baseline' in data
            assert 'analysis' in data
            
            assert data['test_type'] == 'monte_carlo_shuffle'
            assert data['n_simulations'] == stress_test.n_simulations
            
    def test_save_report_markdown_content(self, stress_test, sample_returns):
        """Test contenuto Markdown report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            stress_test.run_shuffle_test(sample_returns, seed=42)
            analysis = stress_test.analyze_results()
            baseline = stress_test.calculate_metrics(sample_returns)

            _, md_path = stress_test.save_report(
                analysis,
                baseline,
                output_dir=tmpdir
            )

            # Leggi Markdown
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verifica sezioni obbligatorie
            assert '# Stress Test Monte Carlo' in content
            assert '## Baseline' in content
            assert '## Distribuzione CAGR' in content
            assert '## Distribuzione MaxDD' in content
            assert '## Gate Criteria' in content
            assert '## Worst Case Scenario' in content
            assert '## Best Case Scenario' in content

            # Verifica conformità DIPF
            assert 'DIPF §9.3' in content
            
    def test_high_volatility_scenario(self, stress_test):
        """Test scenario alta volatilità (dovrebbe fallire gate)"""
        np.random.seed(42)
        # Genera returns con alta volatilità (30% annualized)
        high_vol_returns = np.random.normal(0.0005, 0.02, 252)
        
        stress_test.run_shuffle_test(high_vol_returns, seed=42)
        analysis = stress_test.analyze_results()
        
        # Con alta volatilità, 5th percentile MaxDD dovrebbe essere alto
        assert analysis['gate_criteria']['max_dd_5pct'] > 0.15
        
    def test_low_volatility_scenario(self, stress_test):
        """Test scenario bassa volatilità (dovrebbe passare gate)"""
        np.random.seed(42)
        # Genera returns con bassa volatilità (8% annualized)
        low_vol_returns = np.random.normal(0.0003, 0.005, 252)
        
        stress_test.run_shuffle_test(low_vol_returns, seed=42)
        analysis = stress_test.analyze_results()
        
        # Con bassa volatilità, 5th percentile MaxDD dovrebbe essere basso
        assert analysis['gate_criteria']['max_dd_5pct'] < 0.20
        
    def test_empty_returns_handling(self, stress_test):
        """Test handling returns vuoti"""
        empty_returns = np.array([])
        metrics = stress_test.calculate_metrics(empty_returns)
        
        # Verifica valori default
        assert metrics['cagr'] == 0.0
        assert metrics['max_dd'] == 0.0
        assert metrics['sharpe'] == 0.0
        
    def test_single_return_handling(self, stress_test):
        """Test handling singolo return"""
        single_return = np.array([0.01])
        metrics = stress_test.calculate_metrics(single_return)
        
        # Verifica calcolo corretto
        assert metrics['final_equity'] == 10000.0 * 1.01
        assert metrics['max_dd'] == 0.0  # Nessun drawdown con 1 solo punto
        
    def test_extreme_crash_scenario(self, stress_test):
        """Test scenario crash estremo (-50% in 1 mese)"""
        # Simulazione crash: -3% daily per 20 giorni
        crash_returns = np.full(20, -0.03)
        metrics = stress_test.calculate_metrics(crash_returns)
        
        # Verifica MaxDD > 45%
        assert metrics['max_dd'] > 0.45
        assert metrics['cagr'] < -0.50
        
    def test_recovery_scenario(self, stress_test):
        """Test scenario crash + recovery"""
        # Crash + recovery
        crash = np.full(20, -0.03)  # -50% crash
        recovery = np.full(40, 0.025)  # +100% recovery
        returns = np.concatenate([crash, recovery])
        
        metrics = stress_test.calculate_metrics(returns)
        
        # Verifica MaxDD cattura il crash
        assert metrics['max_dd'] > 0.40
        # Ma final equity dovrebbe essere positivo
        assert metrics['final_equity'] > 10000.0


def test_monte_carlo_integration():
    """Test integrazione completa Monte Carlo"""
    np.random.seed(42)
    
    # Genera returns realistici
    returns = np.random.normal(0.0004, 0.012, 504)  # 2 anni
    
    # Esegui stress test
    stress_test = MonteCarloStressTest(n_simulations=100)
    stress_test.run_shuffle_test(returns, seed=42)
    analysis = stress_test.analyze_results()
    
    # Verifica gate criteria
    gate = analysis['gate_criteria']
    assert 'max_dd_5pct' in gate
    assert 'threshold' in gate
    assert 'passed' in gate
    
    # Verifica distribuzione CAGR
    assert analysis['cagr']['min'] < analysis['cagr']['mean'] < analysis['cagr']['max']
    
    # Verifica distribuzione MaxDD
    assert analysis['max_dd']['min'] < analysis['max_dd']['mean'] < analysis['max_dd']['max']
    
    print(f"\n✅ Test integrazione completato")
    print(f"   5th percentile MaxDD: {gate['max_dd_5pct']*100:.2f}%")
    print(f"   Gate status: {'PASSED' if gate['passed'] else 'FAILED'}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
