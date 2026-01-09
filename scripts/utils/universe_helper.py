#!/usr/bin/env python3
"""Universe Helper - ETF Italia Project

Centralizza lettura universo da config/etf_universe.json.

Supporta strutture diverse (v2/v1/legacy) e fornisce utility
per metadati per-simbolo (es. active_from).

Nota: molte funzioni sono usate dai test. Manteniamo compatibilità
con API precedenti.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _parse_date(value: Any) -> Optional[date]:
    """Parse a YYYY-MM-DD string (or date) into datetime.date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def load_universe_config(path: str | Path) -> Dict[str, Any]:
    """Carica etf_universe.json."""
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _iter_categories(universe: Dict[str, Any]) -> List[str]:
    """Return the ordered list of categories depending on the config structure."""
    # v2
    if 'equity_usa' in universe:
        return ['equity_usa', 'equity_international', 'equity_global', 'bond', 'alternative', 'benchmark']
    # v1
    if 'equity_core' in universe:
        return ['equity_core', 'bond', 'alternative', 'benchmark']
    # legacy
    return ['core', 'satellite', 'bond', 'benchmark']


def iter_universe_etfs(config: Dict[str, Any], include_benchmark: bool = False) -> Iterable[Dict[str, Any]]:
    """Yield ETF entries from config, preserving robust behavior."""
    universe = (config or {}).get('universe', {}) or {}
    categories = _iter_categories(universe)

    for cat in categories:
        if cat == 'benchmark' and not include_benchmark:
            continue
        for etf in universe.get(cat, []) or []:
            if isinstance(etf, dict) and etf.get('symbol'):
                yield etf


def get_universe_symbols(config: Dict[str, Any], include_benchmark: bool = False) -> List[str]:
    """Estrae tutti i simboli dall'universo config in modo robusto."""
    return [e['symbol'] for e in iter_universe_etfs(config, include_benchmark=include_benchmark)]


def get_universe_symbol_meta(
    config: Dict[str, Any],
    include_benchmark: bool = False,
    default_active_from: Optional[date] = None,
) -> List[Tuple[str, Optional[date]]]:
    """Return list of (symbol, active_from).

    active_from is optional; if missing and default_active_from provided, returns default.
    """
    if default_active_from is None:
        # try config defaults
        daf = (config or {}).get('default_active_from') or (config or {}).get('initial_start_date')
        default_active_from = _parse_date(daf)

    out: List[Tuple[str, Optional[date]]] = []
    for e in iter_universe_etfs(config, include_benchmark=include_benchmark):
        sym = e.get('symbol')
        af = _parse_date(e.get('active_from')) or default_active_from
        out.append((sym, af))
    return out


def get_universe_etf_by_symbol(config: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
    """Trova configurazione ETF per simbolo specifico."""
    for e in iter_universe_etfs(config, include_benchmark=True):
        if e.get('symbol') == symbol:
            return e
    return None


def get_symbol_active_from(config: Dict[str, Any], symbol: str) -> Optional[date]:
    etf = get_universe_etf_by_symbol(config, symbol)
    if not etf:
        return None
    # default falls back to config default
    daf = (config or {}).get('default_active_from') or (config or {}).get('initial_start_date')
    return _parse_date(etf.get('active_from')) or _parse_date(daf)


def get_cost_model_for_symbol(config: Dict[str, Any], symbol: str) -> Dict[str, float]:
    """Ottiene cost_model per simbolo specifico."""
    etf = get_universe_etf_by_symbol(config, symbol)

    if etf and 'cost_model' in etf and isinstance(etf['cost_model'], dict):
        return etf['cost_model']

    return {
        'commission_pct': 0.001,
        'slippage_bps': 5,
    }


def get_underlying_for_symbol(config: Dict[str, Any], symbol: str) -> str:
    etf = get_universe_etf_by_symbol(config, symbol)
    if etf:
        return etf.get('underlying') or symbol
    return symbol


def get_ter_for_symbol(config: Dict[str, Any], symbol: str) -> float:
    etf = get_universe_etf_by_symbol(config, symbol)
    if etf and 'ter' in etf:
        try:
            return float(etf['ter'])
        except Exception:
            return 0.001
    return 0.001


def get_execution_model_for_symbol(config: Dict[str, Any], symbol: str) -> Optional[str]:
    etf = get_universe_etf_by_symbol(config, symbol)
    if etf:
        return etf.get('execution_model') or None
    return None
