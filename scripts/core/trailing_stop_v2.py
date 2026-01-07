#!/usr/bin/env python3
"""
Trailing Stop V2 - ETF Italia Project
Implementazione trailing stop con peak tracking (per simbolo) e integrazione con DuckDB.
"""

from __future__ import annotations

from datetime import date


def create_position_peaks_table(conn):
    # Create table if missing
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS position_peaks (
            symbol VARCHAR NOT NULL,
            entry_date DATE NOT NULL,
            entry_price DOUBLE,
            peak_price DOUBLE,
            peak_date DATE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Idempotent migrations (older schemas may be missing columns)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info('position_peaks')").fetchall()]
    except Exception:
        cols = []

    def _add_col(col_name: str, col_type: str):
        if col_name not in cols:
            conn.execute(f"ALTER TABLE position_peaks ADD COLUMN {col_name} {col_type}")
            cols.append(col_name)

    _add_col('entry_price', 'DOUBLE')
    _add_col('peak_price', 'DOUBLE')
    _add_col('peak_date', 'DATE')
    _add_col('created_at', 'TIMESTAMP')

    # Backfill for legacy rows
    try:
        conn.execute("UPDATE position_peaks SET peak_price = COALESCE(peak_price, entry_price)")
        conn.execute("UPDATE position_peaks SET entry_price = COALESCE(entry_price, peak_price)")
        conn.execute("UPDATE position_peaks SET peak_date = COALESCE(peak_date, entry_date)")
    except Exception:
        pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_position_peaks_symbol ON position_peaks(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_position_peaks_active ON position_peaks(is_active)")


def initialize_position_peak(conn, symbol: str, entry_date: date, entry_price: float):
    create_position_peaks_table(conn)

    conn.execute(
        """
        UPDATE position_peaks
        SET is_active = FALSE
        WHERE symbol = ? AND is_active = TRUE
        """,
        [symbol],
    )

    conn.execute(
        """
        INSERT INTO position_peaks (symbol, entry_date, entry_price, peak_price, peak_date, is_active)
        VALUES (?, ?, ?, ?, ?, TRUE)
        """,
        [symbol, entry_date, float(entry_price), float(entry_price), entry_date],
    )


def _get_active_peak(conn, symbol: str):
    create_position_peaks_table(conn)

    row = conn.execute(
        """
        SELECT entry_date, entry_price, peak_price, peak_date
        FROM position_peaks
        WHERE symbol = ? AND is_active = TRUE
        ORDER BY peak_date DESC
        LIMIT 1
        """,
        [symbol],
    ).fetchone()

    if not row:
        return None

    entry_date, entry_price, peak_price, peak_date = row
    return {
        "entry_date": entry_date,
        "entry_price": float(entry_price),
        "peak_price": float(peak_price),
        "peak_date": peak_date,
    }


def update_position_peak(conn, symbol: str, current_price: float, current_date: date):
    peak = _get_active_peak(conn, symbol)

    if peak is None:
        initialize_position_peak(conn, symbol, current_date, current_price)
        return

    if current_price > peak["peak_price"]:
        conn.execute(
            """
            UPDATE position_peaks
            SET peak_price = ?, peak_date = ?
            WHERE symbol = ? AND is_active = TRUE
            """,
            [float(current_price), current_date, symbol],
        )


def check_trailing_stop_v2(conn, config: dict, symbol: str, current_price: float):
    rm = (config or {}).get("risk_management", {})
    cfg = rm.get("trailing_stop_v2", {})

    if not cfg.get("enabled", False):
        return None, None

    peak = _get_active_peak(conn, symbol)
    if peak is None:
        return None, None

    entry_price = peak["entry_price"]
    peak_price = peak["peak_price"]

    if entry_price <= 0 or peak_price <= 0:
        return None, None

    profit_from_entry = (peak_price - entry_price) / entry_price
    min_profit_activation = float(cfg.get("min_profit_activation", 0.0))

    if profit_from_entry < min_profit_activation:
        return None, None

    drawdown = (float(current_price) - peak_price) / peak_price
    drawdown_threshold = float(cfg.get("drawdown_threshold", -0.10))

    if drawdown <= drawdown_threshold:
        return "SELL", f"TRAILING_STOP_V2_DD_{drawdown:.1%}"

    return None, None


def sync_position_peaks_from_ledger(conn):
    """Crea/aggiorna position_peaks per posizioni aperte (net_qty > 0)."""
    create_position_peaks_table(conn)

    open_positions = conn.execute(
        """
        SELECT
            symbol,
            SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) AS net_qty,
            MIN(CASE WHEN type = 'BUY' THEN date ELSE NULL END) AS entry_date,
            AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) AS entry_price
        FROM fiscal_ledger
        WHERE type IN ('BUY', 'SELL')
        GROUP BY symbol
        HAVING net_qty > 0
        """
    ).fetchall()

    for symbol, net_qty, entry_date, entry_price in open_positions:
        if entry_date is None or entry_price is None:
            continue
        if _get_active_peak(conn, symbol) is None:
            initialize_position_peak(conn, symbol, entry_date, float(entry_price))

    # Disattiva peaks per simboli senza posizione
    active_symbols = {row[0] for row in open_positions}
    conn.execute(
        """
        UPDATE position_peaks
        SET is_active = FALSE
        WHERE is_active = TRUE
          AND symbol NOT IN (SELECT DISTINCT symbol FROM fiscal_ledger WHERE type IN ('BUY','SELL'))
        """
    )
