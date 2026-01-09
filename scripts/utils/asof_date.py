#!/usr/bin/env python3
"""utils.asof_date - ETF Italia Project

Centralizza la logica per scegliere una data "as-of" coerente, evitando:
- future leak (ledger date > market_data max-date)
- look-ahead (uso di prezzi futuri)
- trading su giorni calendar-open ma senza dati

La scelta è basata su una soglia di copertura (es. 0.8 = 80% simboli con dati).
"""

from __future__ import annotations

import math
from typing import List, Optional

def compute_asof_date(conn, symbols: List[str], coverage_threshold: float = 0.8, venue: str = 'BIT'):
    """Restituisce l'ultima data 'tradabile' coerente per un set di simboli.

    Requisiti:
      - trading_calendar.is_open = TRUE per il venue scelto
      - market_data coverage >= ceil(threshold * n_symbols)
      - signals coverage >= ceil(threshold * n_symbols) (se la tabella signals esiste)

    Args:
      conn: duckdb connection
      symbols: lista simboli (escludere benchmark se non rilevante)
      coverage_threshold: 0..1
      venue: trading venue

    Returns:
      datetime.date oppure None se non disponibile
    """
    if not symbols:
        return conn.execute("SELECT MAX(date) FROM market_data").fetchone()[0]

    threshold = float(coverage_threshold) if coverage_threshold is not None else 0.8
    threshold = max(0.0, min(1.0, threshold))
    min_required = max(1, int(math.ceil(threshold * len(symbols))))

    placeholders = ",".join(["?"] * len(symbols))

    # signals potrebbe non esistere in contesti minimali → fallback su market_data
    signals_exists = False
    try:
        conn.execute("SELECT 1 FROM signals LIMIT 1").fetchone()
        signals_exists = True
    except Exception:
        signals_exists = False

    if signals_exists:
        sql = f"""
        WITH md_counts AS (
            SELECT date, COUNT(DISTINCT symbol) AS md_cnt
            FROM market_data
            WHERE symbol IN ({placeholders})
            GROUP BY date
        ),
        sig_counts AS (
            SELECT date, COUNT(DISTINCT symbol) AS sig_cnt
            FROM signals
            WHERE symbol IN ({placeholders})
            GROUP BY date
        )
        SELECT MAX(md.date)
        FROM md_counts md
        JOIN sig_counts sc ON sc.date = md.date
        JOIN trading_calendar tc ON tc.date = md.date AND tc.venue = ? AND tc.is_open = TRUE
        WHERE md.md_cnt >= ? AND sc.sig_cnt >= ?
        """
        params = list(symbols) + list(symbols) + [venue, min_required, min_required]
        asof = conn.execute(sql, params).fetchone()[0]
        if asof:
            return asof

    # Fallback: solo market_data + calendar
    sql2 = f"""
    WITH md_counts AS (
        SELECT date, COUNT(DISTINCT symbol) AS md_cnt
        FROM market_data
        WHERE symbol IN ({placeholders})
        GROUP BY date
    )
    SELECT MAX(md.date)
    FROM md_counts md
    JOIN trading_calendar tc ON tc.date = md.date AND tc.venue = ? AND tc.is_open = TRUE
    WHERE md.md_cnt >= ?
    """
    params2 = list(symbols) + [venue, min_required]
    asof2 = conn.execute(sql2, params2).fetchone()[0]
    if asof2:
        return asof2

    # Estremo fallback: max market_data globale
    return conn.execute("SELECT MAX(date) FROM market_data").fetchone()[0]
