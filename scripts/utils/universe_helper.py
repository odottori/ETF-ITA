#!/usr/bin/env python3
"""
Universe Helper - ETF Italia Project
Funzione centralizzata per leggere simboli da config universe
Supporta tutte le strutture: v2 (equity_usa, etc), v1 (equity_core), legacy (core/satellite)
"""

def get_universe_symbols(config, include_benchmark=False):
    """
    Estrae tutti i simboli dall'universo config
    
    Args:
        config: Configurazione caricata da etf_universe.json
        include_benchmark: Se True, include anche simboli benchmark
    
    Returns:
        list: Lista simboli ETF
    """
    symbols = []
    universe = config.get('universe', {})
    
    # Nuova struttura v2 (equity_usa, equity_international, equity_global, bond, alternative)
    if 'equity_usa' in universe:
        symbols.extend([etf['symbol'] for etf in universe.get('equity_usa', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('equity_international', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('equity_global', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('bond', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('alternative', [])])
    
    # Struttura v1 (equity_core, bond, alternative)
    elif 'equity_core' in universe:
        symbols.extend([etf['symbol'] for etf in universe.get('equity_core', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('bond', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('alternative', [])])
    
    # Vecchia struttura (core, satellite, bond)
    else:
        symbols.extend([etf['symbol'] for etf in universe.get('core', [])])
        symbols.extend([etf['symbol'] for etf in universe.get('satellite', [])])
        if 'bond' in universe:
            symbols.extend([etf['symbol'] for etf in universe.get('bond', [])])
    
    # Benchmark opzionale
    if include_benchmark and 'benchmark' in universe:
        symbols.extend([etf['symbol'] for etf in universe.get('benchmark', [])])
    
    return symbols


def get_universe_etf_by_symbol(config, symbol):
    """
    Trova configurazione ETF per simbolo specifico
    
    Args:
        config: Configurazione caricata da etf_universe.json
        symbol: Simbolo ETF da cercare
    
    Returns:
        dict: Configurazione ETF o None se non trovato
    """
    universe = config.get('universe', {})
    
    # Cerca in tutte le categorie
    all_categories = []
    
    if 'equity_usa' in universe:
        all_categories = ['equity_usa', 'equity_international', 'equity_global', 'bond', 'alternative', 'benchmark']
    elif 'equity_core' in universe:
        all_categories = ['equity_core', 'bond', 'alternative', 'benchmark']
    else:
        all_categories = ['core', 'satellite', 'bond', 'benchmark']
    
    for category in all_categories:
        if category in universe:
            for etf in universe[category]:
                if etf['symbol'] == symbol:
                    return etf
    
    return None


def get_cost_model_for_symbol(config, symbol):
    """
    Ottiene cost_model per simbolo specifico
    
    Args:
        config: Configurazione caricata da etf_universe.json
        symbol: Simbolo ETF
    
    Returns:
        dict: cost_model con commission_pct e slippage_bps
    """
    etf = get_universe_etf_by_symbol(config, symbol)
    
    if etf and 'cost_model' in etf:
        return etf['cost_model']
    
    # Fallback default
    return {
        'commission_pct': 0.001,
        'slippage_bps': 5
    }
