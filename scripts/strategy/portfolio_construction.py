#!/usr/bin/env python3
"""
Portfolio Construction & Holding Period Logic - ETF Italia Project v10
Implementa ranking candidati, allocation logic e holding period dinamico
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def calculate_expected_holding_days(
    risk_scalar: float,
    volatility: float,
    momentum_score: float,
    signal_state: str,
    config: dict
) -> int:
    """
    Calcola holding period dinamico per MULTI-DAY TRADING (1-30gg)
    Design v2.1: LOGICA INVERTITA - alto momentum/risk/vol = holding CORTO
    Range target: 5-30 giorni per swing trading
    
    Args:
        risk_scalar: Risk scalar (0-1)
        volatility: Volatilità annualizzata (es. 0.15 = 15%)
        momentum_score: Momentum score (0-1)
        signal_state: Signal state (RISK_ON/RISK_OFF/NEUTRAL)
        config: Config dict con holding_period params
        
    Returns:
        Holding days (clamped tra min e max)
    """
    holding_cfg = config.get('holding_period', {})
    base_days = holding_cfg.get('base_holding_days', 15)  # Base per multi-day
    min_days = holding_cfg.get('min_holding_days', 5)     # Min swing trading
    max_days = holding_cfg.get('max_holding_days', 30)    # Max ~1 mese
    
    # Risk adjustment: INVERTITO - alto risk = holding CORTO (prendi profitto veloce)
    # Nota: la tabella signals usa anche 'HOLD' (trattato come NEUTRAL)
    if signal_state == 'RISK_OFF':
        risk_adj = 1.5  # Più lungo, aspetta recovery
    elif signal_state in ('NEUTRAL', 'HOLD'):
        risk_adj = 1.2 - 0.2 * risk_scalar  # 1.0..1.2
    else:  # RISK_ON
        risk_adj = 1.0 - 0.3 * risk_scalar  # 0.7..1.0 (più risk = più corto)
    
    # Volatility adjustment: INVERTITO - alta vol = holding CORTO (rischio maggiore)
    if volatility >= 0.25:
        vol_adj = 0.60  # Alta vol → exit veloce
    elif volatility >= 0.18:
        vol_adj = 0.80
    else:
        vol_adj = 1.00  # Bassa vol → può tenere
    
    # Momentum adjustment: INVERTITO - alto momentum = holding CORTO (prendi profitto)
    if momentum_score >= 0.85:
        momentum_adj = 0.70  # Momentum forte → prendi profitto veloce
    elif momentum_score >= 0.70:
        momentum_adj = 0.85
    elif momentum_score >= 0.55:
        momentum_adj = 1.00
    else:
        momentum_adj = 1.20  # Momentum debole → aspetta
    
    # Calcolo finale con clamp
    holding_days = base_days * risk_adj * vol_adj * momentum_adj
    
    return int(max(min_days, min(max_days, holding_days)))


def calculate_cost_penalty(
    ter: float,
    slippage_bps: float,
    config: dict
) -> float:
    """
    Calcola penalty per costi (TER + slippage) normalizzata 0-1
    Design v2.0: penalty, non gating monetario
    
    Args:
        ter: Total Expense Ratio annuale (es. 0.0007 = 0.07%)
        slippage_bps: Slippage in basis points (es. 5 = 5bps)
        config: Config dict
        
    Returns:
        Cost penalty (0-1, higher = more expensive)
    """
    # TER annuale + slippage round-trip (2x)
    total_cost_pct = ter + (slippage_bps * 2 / 10000)
    
    # Normalizza: 0% = 0 penalty, 1% = 1 penalty (max realistico per ETF)
    penalty = min(1.0, total_cost_pct / 0.01)
    
    return max(0.0, penalty)


def calculate_overlap_penalty(
    symbol: str,
    current_positions: Dict[str, dict],
    underlying_map: Dict[str, str],
    config: dict
) -> float:
    """
    Calcola penalty per overlap underlying
    Design v2.0: default FORBID (penalty = 1.0 se overlap)
    
    Args:
        symbol: Simbolo candidato
        current_positions: Dict posizioni aperte
        underlying_map: Dict {symbol: underlying} (es. {'XS2L.MI': 'SP500', 'CSSPX.MI': 'SP500'})
        config: Config dict
        
    Returns:
        Overlap penalty (0 = no overlap, 1 = overlap forbidden)
    """
    exec_cfg = config.get('execution', {})
    forbid_overlap = exec_cfg.get('forbid_overlap_underlying', True)
    
    if not forbid_overlap:
        return 0.0  # Overlap permesso
    
    # Check overlap
    candidate_underlying = underlying_map.get(symbol, symbol)
    
    for pos_symbol in current_positions.keys():
        pos_underlying = underlying_map.get(pos_symbol, pos_symbol)
        if candidate_underlying == pos_underlying:
            return 1.0  # Overlap detected → penalty massima
    
    return 0.0  # No overlap


def calculate_candidate_score(
    momentum_score: float,
    risk_scalar: float,
    volatility: float,
    ter: float,
    slippage_bps: float,
    symbol: str,
    current_positions: Dict[str, dict],
    underlying_map: Dict[str, str],
    config: dict
) -> float:
    """
    Calcola score composito per ranking candidati
    Design v2.0: alpha DEPRECATO, aggiunti cost_penalty e overlap_penalty
    
    Args:
        momentum_score: Momentum score (0-1)
        risk_scalar: Risk scalar (0-1)
        volatility: Volatilità annualizzata (0-1)
        ter: Total Expense Ratio
        slippage_bps: Slippage in bps
        symbol: Simbolo candidato
        current_positions: Dict posizioni aperte
        underlying_map: Dict symbol->underlying
        config: Config dict con ranking_weights
        
    Returns:
        Candidate score (0-1, higher is better)
    """
    weights = config.get('ranking_weights', {})
    w_momentum = weights.get('momentum', 0.45)
    w_risk = weights.get('risk_scalar', 0.25)
    w_vol = weights.get('volatility', 0.20)
    w_cost = weights.get('cost_penalty', 0.05)
    w_overlap = weights.get('overlap_penalty', 0.05)
    w_alpha = weights.get('alpha', 0.00)  # DEPRECATED
    
    # Normalizza volatilità (inverso, max 30%)
    vol_normalized = max(0, min(1, 1 - (volatility / 0.30)))
    
    # Calcola penalty
    cost_penalty = calculate_cost_penalty(ter, slippage_bps, config)
    overlap_penalty = calculate_overlap_penalty(symbol, current_positions, underlying_map, config)
    
    # Score composito (penalty sottratte)
    score = (
        momentum_score * w_momentum +
        risk_scalar * w_risk +
        vol_normalized * w_vol -
        cost_penalty * w_cost -
        overlap_penalty * w_overlap
    )
    
    # Clamp finale [0, 1]
    return max(0.0, min(1.0, score))


def rank_candidates(
    candidates: List[str],
    signals_data: Dict[str, dict],
    current_positions: Dict[str, dict],
    underlying_map: Dict[str, str],
    config: dict
) -> List[Tuple[str, float]]:
    """
    Ordina candidati per score decrescente
    Design v2.0: include cost_penalty e overlap_penalty
    
    Args:
        candidates: Lista simboli candidati
        signals_data: Dict {symbol: {momentum_score, risk_scalar, volatility, ter, slippage_bps, ...}}
        current_positions: Dict posizioni aperte
        underlying_map: Dict symbol->underlying
        config: Config dict
        
    Returns:
        Lista di tuple (symbol, score) ordinata per score decrescente
    """
    ranked = []
    
    for symbol in candidates:
        signal = signals_data.get(symbol, {})
        
        momentum_score = signal.get('momentum_score', 0.0)
        risk_scalar = signal.get('risk_scalar', 0.0)
        volatility = signal.get('volatility', 0.15)
        ter = signal.get('ter', 0.001)
        slippage_bps = signal.get('slippage_bps', 5)
        
        score = calculate_candidate_score(
            momentum_score,
            risk_scalar,
            volatility,
            ter,
            slippage_bps,
            symbol,
            current_positions,
            underlying_map,
            config
        )
        
        ranked.append((symbol, score))
    
    # Ordina per score decrescente
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return ranked


def get_current_positions(conn, run_type: str = 'BACKTEST') -> Dict[str, dict]:
    """
    Ottiene posizioni aperte correnti dal fiscal_ledger
    
    Args:
        conn: DuckDB connection
        run_type: Tipo run (BACKTEST o PRODUCTION)
        
    Returns:
        Dict {symbol: {qty, entry_date, entry_score, expected_holding_days, expected_exit_date}}
    """
    query = """
    WITH position_entries AS (
        SELECT 
            symbol,
            date as entry_date,
            price as entry_price,
            qty,
            entry_score,
            expected_holding_days,
            expected_exit_date,
            type
        FROM fiscal_ledger
        WHERE run_type = ?
          AND type IN ('BUY', 'SELL')
    )
    SELECT 
        symbol,
        SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as total_qty,
        MIN(entry_date) as first_entry_date,
        SUM(CASE WHEN type = 'BUY' THEN qty * entry_price ELSE 0 END) / 
            NULLIF(SUM(CASE WHEN type = 'BUY' THEN qty ELSE 0 END), 0) as avg_entry_price,
        AVG(CASE WHEN type = 'BUY' THEN entry_score ELSE NULL END) as avg_entry_score,
        AVG(CASE WHEN type = 'BUY' THEN expected_holding_days ELSE NULL END) as avg_expected_holding_days,
        MAX(expected_exit_date) as latest_expected_exit_date
    FROM position_entries
    GROUP BY symbol
    HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) > 0
    """
    
    result = conn.execute(query, [run_type]).fetchall()
    
    positions = {}
    for row in result:
        symbol, qty, entry_date, entry_price, entry_score, exp_holding, exp_exit = row
        positions[symbol] = {
            'qty': qty,
            'entry_date': entry_date,
            'entry_price': entry_price if entry_price else 0.0,
            'entry_score': entry_score if entry_score else 0.0,
            'expected_holding_days': int(exp_holding) if exp_holding else 90,
            'expected_exit_date': exp_exit
        }
    
    return positions


def calculate_available_cash(conn, portfolio_value: float, config: dict, run_type: str = 'BACKTEST') -> float:
    """
    Calcola cash disponibile dopo reserve
    
    Args:
        conn: DuckDB connection
        portfolio_value: Valore totale portfolio
        config: Config dict
        run_type: Tipo run
        
    Returns:
        Cash disponibile per nuovi entry
    """
    # Calcola cash balance corrente
    query = """
    SELECT COALESCE(SUM(CASE 
        WHEN type = 'DEPOSIT' THEN qty * price
        WHEN type = 'SELL' THEN qty * price - fees - tax_paid
        WHEN type = 'BUY' THEN -(qty * price + fees)
        WHEN type = 'INTEREST' THEN qty
        ELSE 0 
    END), 0) as cash
    FROM fiscal_ledger
    WHERE run_type = ?
    """
    
    cash_balance = conn.execute(query, [run_type]).fetchone()[0]
    
    # Reserve minimo
    min_cash_reserve_pct = config.get('portfolio_construction', {}).get('min_cash_reserve_pct', 0.10)
    min_reserve = portfolio_value * min_cash_reserve_pct
    
    # Cash disponibile
    available = cash_balance - min_reserve
    
    return max(0.0, available)


def filter_by_constraints(
    ranked_candidates: List[Tuple[str, float]],
    current_positions: Dict[str, dict],
    available_cash: float,
    current_date: datetime.date,
    config: dict
) -> List[Tuple[str, float]]:
    """
    Filtra candidati per constraints (max positions, cash, overlap)
    
    Args:
        ranked_candidates: Lista (symbol, score) ordinata
        current_positions: Dict posizioni aperte
        available_cash: Cash disponibile
        current_date: Data corrente
        config: Config dict
        
    Returns:
        Lista candidati filtrati
    """
    portfolio_cfg = config.get('portfolio_construction', {})
    max_open_positions = portfolio_cfg.get('max_open_positions', 3)
    min_trade_value = portfolio_cfg.get('min_trade_value', 2000)
    score_add_threshold = portfolio_cfg.get('score_add_threshold', 1.2)
    score_entry_min = config.get('settings', {}).get('score_entry_min', 0.7)
    
    # Check 1: Max positions
    if len(current_positions) >= max_open_positions:
        # Skip tutti i nuovi entry, considera solo rebalancing posizioni esistenti
        return []
    
    # Check 2: Cash disponibile
    if available_cash < min_trade_value:
        return []
    
    # Check 3: Overlap e score filtering
    filtered = []
    
    for symbol, score in ranked_candidates:
        # Score minimo per entry
        if score < score_entry_min:
            continue
        
        # Check overlap
        if symbol in current_positions:
            position = current_positions[symbol]
            
            # Calcola days_held
            days_held = (current_date - position['entry_date']).days
            expected_holding = position['expected_holding_days']
            
            # Troppo presto per aggiungere (< 50% holding)
            if days_held < expected_holding * 0.5:
                continue
            
            # Score non migliorato abbastanza
            entry_score = position['entry_score']
            if score < entry_score * score_add_threshold:
                continue
            
            # OK: scenario migliorato significativamente
            filtered.append((symbol, score))
        else:
            # Nuova posizione OK
            filtered.append((symbol, score))
    
    return filtered


def should_extend_holding(
    position: dict,
    current_signal: dict,
    current_date: datetime.date,
    config: dict
) -> Tuple[bool, Optional[int]]:
    """
    Decide se estendere holding di una posizione a scadenza
    Design v2.1: Aggiunte logiche take profit e max extensions per multi-day trading
    
    Args:
        position: Dict posizione {entry_date, expected_holding_days, ...}
        current_signal: Dict segnale corrente {signal_state, momentum_score, risk_scalar, ...}
        current_date: Data corrente
        config: Config dict
        
    Returns:
        (should_extend, new_holding_days)
    """
    score_entry_min = config.get('settings', {}).get('score_entry_min', 0.7)
    
    # Check 1: Scenario ancora favorevole?
    signal_state = current_signal.get('signal_state', 'HOLD')
    momentum_score = current_signal.get('momentum_score', 0.0)
    
    if signal_state != 'RISK_ON':
        return (False, None)
    
    if momentum_score < score_entry_min:
        return (False, None)
    
    # Check 2: Max extensions solo per casi estremi (6 mesi)
    entry_date = position.get('entry_date')
    if entry_date:
        days_held = (current_date - entry_date).days
        absolute_max = 180  # 6 mesi massimo assoluto
        if days_held >= absolute_max:
            return (False, None)  # Forza exit dopo 6 mesi
    
    # Check 3: Momentum degrading rimosso - TP/SL gestiscono exit
    # Sistema usa solo PASS 1A (TP/SL/guardrails) per exit decisions
    
    # Check 4: Calcola nuovo holding con condizioni aggiornate
    risk_scalar = current_signal.get('risk_scalar', 0.5)
    volatility = current_signal.get('volatility', 0.15)
    
    new_holding_days = calculate_expected_holding_days(
        risk_scalar,
        volatility,
        momentum_score,
        signal_state,
        config
    )
    
    return (True, new_holding_days)


def calculate_qty(
    symbol: str,
    price: float,
    available_cash: float,
    portfolio_value: float,
    risk_scalar: float,
    config: dict
) -> int:
    """
    Calcola qty da acquistare per un simbolo
    
    Args:
        symbol: Simbolo
        price: Prezzo corrente
        available_cash: Cash disponibile
        portfolio_value: Valore totale portfolio
        risk_scalar: Risk scalar
        config: Config dict
        
    Returns:
        Qty (int)
    """
    portfolio_cfg = config.get('portfolio_construction', {})
    max_open_positions = portfolio_cfg.get('max_open_positions', 3)
    
    # Base weight (equal weight tra max positions)
    base_weight = 1.0 / max_open_positions
    
    # Target weight modulato da risk_scalar
    target_weight = base_weight * risk_scalar
    
    # Target value
    target_value = portfolio_value * target_weight
    
    # Qty
    qty = int(target_value / price)
    
    # Constraint: non superare cash disponibile
    if qty * price > available_cash:
        qty = int(available_cash / price)
    
    return max(0, qty)


def get_positions_for_review(
    conn,
    current_date: datetime.date,
    run_type: str = 'BACKTEST'
) -> List[dict]:
    """
    Ottiene posizioni che richiedono riesame (holding scaduto o prossimo alla scadenza)
    
    Args:
        conn: DuckDB connection
        current_date: Data corrente
        run_type: Tipo run
        
    Returns:
        Lista posizioni da riesaminare
    """
    query = """
    WITH position_entries AS (
        SELECT 
            symbol,
            date as entry_date,
            entry_score,
            expected_holding_days,
            expected_exit_date,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty
        FROM fiscal_ledger
        WHERE run_type = ?
          AND type IN ('BUY', 'SELL')
        GROUP BY symbol, date, entry_score, expected_holding_days, expected_exit_date
    ),
    current_positions AS (
        SELECT 
            symbol,
            SUM(qty) as total_qty,
            MIN(entry_date) as first_entry_date,
            AVG(entry_score) as avg_entry_score,
            AVG(expected_holding_days) as avg_expected_holding_days,
            MAX(expected_exit_date) as latest_expected_exit_date
        FROM position_entries
        GROUP BY symbol
        HAVING SUM(qty) > 0
    )
    SELECT 
        symbol,
        total_qty,
        first_entry_date,
        avg_entry_score,
        avg_expected_holding_days,
        latest_expected_exit_date
    FROM current_positions
    WHERE latest_expected_exit_date <= ?
    """
    
    result = conn.execute(query, [run_type, current_date]).fetchall()
    
    positions = []
    for row in result:
        symbol, qty, entry_date, entry_score, exp_holding, exp_exit = row
        positions.append({
            'symbol': symbol,
            'qty': qty,
            'entry_date': entry_date,
            'entry_score': entry_score if entry_score else 0.0,
            'expected_holding_days': int(exp_holding) if exp_holding else 90,
            'expected_exit_date': exp_exit
        })
    
    return positions
