#!/usr/bin/env python3
"""
Test Suite - Holding Period v2.0
Unit tests + Property tests per portfolio_construction.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.strategy.portfolio_construction import (
    calculate_expected_holding_days,
    calculate_cost_penalty,
    calculate_overlap_penalty,
    calculate_candidate_score
)

def test_holding_period_range():
    """Test: holding period sempre in range [5, 30] (multi-day swing trading)"""
    
    config = {
        'holding_period': {
            'base_holding_days': 15,
            'min_holding_days': 5,
            'max_holding_days': 30
        }
    }
    
    # Test casi estremi
    test_cases = [
        # (risk_scalar, volatility, momentum_score, signal_state, expected_min, expected_max)
        (1.0, 0.10, 0.90, 'RISK_ON', 5, 30),     # Max convinzione (holding corto)
        (0.0, 0.30, 0.20, 'RISK_OFF', 5, 30),    # RISK_OFF (holding lungo)
        (0.5, 0.18, 0.60, 'HOLD', 5, 30),        # HOLD trattato come NEUTRAL
    ]
    
    for risk_scalar, vol, momentum, signal_state, exp_min, exp_max in test_cases:
        holding = calculate_expected_holding_days(
            risk_scalar, vol, momentum, signal_state, config
        )
        
        assert exp_min <= holding <= exp_max, \
            f"Holding {holding} fuori range [{exp_min}, {exp_max}] per {signal_state}"
        
        print(f"  ✅ {signal_state}: risk={risk_scalar:.1f}, vol={vol:.0%}, momentum={momentum:.1f} → {holding}d")
    
    print("✅ test_holding_period_range PASSED")


def test_cost_penalty_range():
    """Test: cost_penalty sempre in range [0, 1]"""
    
    config = {}
    
    test_cases = [
        (0.0001, 2),   # ETF economico
        (0.0035, 8),   # ETF costoso (leveraged)
        (0.0100, 20),  # Caso estremo
    ]
    
    for ter, slippage_bps in test_cases:
        penalty = calculate_cost_penalty(ter, slippage_bps, config)
        
        assert 0.0 <= penalty <= 1.0, \
            f"Cost penalty {penalty} fuori range [0, 1]"
        
        print(f"  ✅ TER={ter:.2%}, slippage={slippage_bps}bps → penalty={penalty:.3f}")
    
    print("✅ test_cost_penalty_range PASSED")


def test_overlap_penalty_forbid():
    """Test: overlap penalty = 1.0 se overlap e forbid=True"""
    
    config = {
        'execution': {
            'forbid_overlap_underlying': True
        }
    }
    
    current_positions = {'CSSPX.MI': {}}
    underlying_map = {
        'CSSPX.MI': 'SP500',
        'XS2L.MI': 'SP500',  # Stesso underlying
        'EIMI.MI': 'MSCI_EM'  # Diverso underlying
    }
    
    # Test overlap
    penalty_overlap = calculate_overlap_penalty('XS2L.MI', current_positions, underlying_map, config)
    assert penalty_overlap == 1.0, f"Expected penalty=1.0 per overlap, got {penalty_overlap}"
    print(f"  ✅ XS2L.MI (overlap SP500) → penalty={penalty_overlap}")
    
    # Test no overlap
    penalty_no_overlap = calculate_overlap_penalty('EIMI.MI', current_positions, underlying_map, config)
    assert penalty_no_overlap == 0.0, f"Expected penalty=0.0 per no overlap, got {penalty_no_overlap}"
    print(f"  ✅ EIMI.MI (no overlap) → penalty={penalty_no_overlap}")
    
    print("✅ test_overlap_penalty_forbid PASSED")


def test_candidate_score_range():
    """Test: candidate_score sempre in range [0, 1]"""
    
    config = {
        'ranking_weights': {
            'momentum': 0.45,
            'risk_scalar': 0.25,
            'volatility': 0.20,
            'cost_penalty': 0.05,
            'overlap_penalty': 0.05,
            'alpha': 0.00
        },
        'execution': {
            'forbid_overlap_underlying': True
        }
    }
    
    current_positions = {}
    underlying_map = {}
    
    test_cases = [
        # (momentum, risk, vol, ter, slippage, symbol)
        (0.80, 0.90, 0.12, 0.0007, 5, 'ETF_A'),  # High score
        (0.30, 0.40, 0.25, 0.0035, 8, 'ETF_B'),  # Low score
        (0.60, 0.70, 0.18, 0.0010, 5, 'ETF_C'),  # Medium score
    ]
    
    for momentum, risk, vol, ter, slippage, symbol in test_cases:
        score = calculate_candidate_score(
            momentum, risk, vol, ter, slippage,
            symbol, current_positions, underlying_map, config
        )
        
        assert 0.0 <= score <= 1.0, \
            f"Score {score} fuori range [0, 1] per {symbol}"
        
        print(f"  ✅ {symbol}: momentum={momentum:.2f}, risk={risk:.2f} → score={score:.3f}")
    
    print("✅ test_candidate_score_range PASSED")


def test_property_score_monotonic():
    """Property test: score aumenta con momentum/risk, diminuisce con vol/cost"""
    
    config = {
        'ranking_weights': {
            'momentum': 0.45,
            'risk_scalar': 0.25,
            'volatility': 0.20,
            'cost_penalty': 0.05,
            'overlap_penalty': 0.05,
            'alpha': 0.00
        },
        'execution': {'forbid_overlap_underlying': False}
    }
    
    current_positions = {}
    underlying_map = {}
    
    # Base case
    base_score = calculate_candidate_score(
        0.60, 0.70, 0.15, 0.001, 5,
        'BASE', current_positions, underlying_map, config
    )
    
    # Aumenta momentum → score aumenta
    higher_momentum_score = calculate_candidate_score(
        0.80, 0.70, 0.15, 0.001, 5,
        'HIGH_MOM', current_positions, underlying_map, config
    )
    assert higher_momentum_score > base_score, "Score non aumenta con momentum"
    print(f"  ✅ Momentum ↑: {base_score:.3f} → {higher_momentum_score:.3f}")
    
    # Aumenta volatilità → score diminuisce
    higher_vol_score = calculate_candidate_score(
        0.60, 0.70, 0.25, 0.001, 5,
        'HIGH_VOL', current_positions, underlying_map, config
    )
    assert higher_vol_score < base_score, "Score non diminuisce con volatilità"
    print(f"  ✅ Volatility ↑: {base_score:.3f} → {higher_vol_score:.3f}")
    
    # Aumenta costi → score diminuisce
    higher_cost_score = calculate_candidate_score(
        0.60, 0.70, 0.15, 0.005, 15,
        'HIGH_COST', current_positions, underlying_map, config
    )
    assert higher_cost_score < base_score, "Score non diminuisce con costi"
    print(f"  ✅ Cost ↑: {base_score:.3f} → {higher_cost_score:.3f}")
    
    print("✅ test_property_score_monotonic PASSED")


def run_all_tests():
    """Esegue tutti i test"""
    
    print("\n" + "=" * 60)
    print("TEST SUITE - Holding Period v2.0")
    print("=" * 60 + "\n")
    
    tests = [
        ("Holding Period Range", test_holding_period_range),
        ("Cost Penalty Range", test_cost_penalty_range),
        ("Overlap Penalty Forbid", test_overlap_penalty_forbid),
        ("Candidate Score Range", test_candidate_score_range),
        ("Property: Score Monotonic", test_property_score_monotonic),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n🧪 {name}")
            print("-" * 60)
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RISULTATI: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
