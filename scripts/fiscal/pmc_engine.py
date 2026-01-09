#!/usr/bin/env python3
"""PMC (Prezzo Medio di Carico) engine.

Questo modulo fornisce una logica minimale ma coerente per:
- calcolare posizione aperta e costo medio (PMC) per simbolo, per run_type
- stimare gain/loss realizzati in SELL considerando fees

Assunzioni:
- Cost basis: metodo "costo medio" (PMC) su base contabile.
- Le fees di BUY aumentano il costo (allocazione per share).
- Le fees di SELL riducono il proceeds (quindi riducono il gain).

Nota: Non gestisce lotti FIFO/Specific ID; è una scelta esplicita per semplicità.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


def _has_column(conn, table: str, col: str) -> bool:
    """True se la tabella contiene la colonna (DuckDB)."""
    try:
        cols = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        return col in {c[1] for c in cols}
    except Exception:
        return False



@dataclass
class PositionState:
    symbol: str
    qty: float
    total_cost: float  # costo contabile complessivo (include fees BUY), in EUR

    @property
    def pmc(self) -> float:
        if self.qty <= 0:
            return 0.0
        return self.total_cost / self.qty


def load_position_state(conn, symbol: str, run_type: str = "PRODUCTION") -> PositionState:
    """Ricostruisce qty e total_cost dal fiscal_ledger per un simbolo.

    Nota: alcuni test/unit DB minimali non hanno la colonna run_type. In quel caso,
    la ricostruzione viene fatta senza filtro run_type.
    """

    if _has_column(conn, 'fiscal_ledger', 'run_type'):
        rows = conn.execute(
            """
            SELECT id, date, type, qty, price, COALESCE(fees, 0) as fees
            FROM fiscal_ledger
            WHERE symbol = ?
              AND type IN ('BUY', 'SELL')
              AND COALESCE(run_type, 'PRODUCTION') = ?
            ORDER BY date ASC, id ASC
            """,
            [symbol, run_type],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, date, type, qty, price, COALESCE(fees, 0) as fees
            FROM fiscal_ledger
            WHERE symbol = ?
              AND type IN ('BUY', 'SELL')
            ORDER BY date ASC, id ASC
            """,
            [symbol],
        ).fetchall()

    qty = 0.0
    total_cost = 0.0

    for _id, _dt, typ, q, p, fees in rows:
        q = float(q)
        p = float(p)
        fees = float(fees or 0.0)

        if typ == "BUY":
            # costo aumenta di controvalore + fees
            total_cost += q * p + fees
            qty += q
        elif typ == "SELL":
            # riduce qty e rimuove costo proporzionale a PMC corrente
            if qty <= 0:
                # oversell storico: lascia invariato (sanity_check dovrebbe bloccare)
                continue
            q_sell = min(q, qty)
            pmc = total_cost / qty if qty > 0 else 0.0
            total_cost -= pmc * q_sell
            qty -= q_sell
            if qty <= 1e-12:
                qty = 0.0
                total_cost = 0.0

    return PositionState(symbol=symbol, qty=qty, total_cost=total_cost)


def apply_buy(state: PositionState, qty: float, price: float, fees: float) -> PositionState:
    qty = float(qty)
    price = float(price)
    fees = float(fees or 0.0)
    return PositionState(
        symbol=state.symbol,
        qty=state.qty + qty,
        total_cost=state.total_cost + qty * price + fees,
    )


def estimate_sell_gain(
    state: PositionState,
    qty_to_sell: float,
    sell_price: float,
    sell_fees: float,
) -> Tuple[float, float]:
    """Ritorna (realized_gain, pmc_used)."""
    qty_to_sell = float(qty_to_sell)
    sell_price = float(sell_price)
    sell_fees = float(sell_fees or 0.0)

    if state.qty <= 0:
        return 0.0, 0.0

    q = min(qty_to_sell, state.qty)
    pmc = state.pmc

    proceeds = q * sell_price - sell_fees
    cost_removed = q * pmc
    realized = proceeds - cost_removed
    return realized, pmc
