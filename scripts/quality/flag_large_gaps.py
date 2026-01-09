#!/usr/bin/env python3
"""scripts/quality/flag_large_gaps.py

Flag "universe-wide" calendar gaps as `large_gap` (safe remediation).

Definition (bounded):
- Consider trading_calendar days where `is_open = TRUE` for a venue
- Bound the scan to `max(market_data.date)` for the universe symbols
- A day is a "universe-wide gap" if **none** of the universe symbols have market_data on that date

Apply action (when --apply):
- `is_open = FALSE`
- `quality_flag = 'large_gap'` (if the column exists)
- `reason = 'universe_wide_no_market_data'` (if the column exists)

This matches the "disaster/outage -> no-trade until healed" philosophy, applied to history.

Usage:
  py scripts/quality/flag_large_gaps.py                 # dry-run
  py scripts/quality/flag_large_gaps.py --apply         # apply

Optional:
  set ETF_VENUE=BIT|XMIL
  py scripts/quality/flag_large_gaps.py --venue BIT --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import duckdb


def _bootstrap_paths() -> Path:
    """Ensure repo root + scripts/ are on sys.path."""
    root = Path(__file__).resolve().parents[2]
    scripts_dir = root / "scripts"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return root


def _load_universe_symbols(root: Path) -> list[str]:
    """Best-effort universe symbol discovery.

    Priority:
      1) config/etf_universe.json via utils.universe_helper
      2) fallback: top 5 '.MI' symbols by coverage in market_data
    """
    cfg_path = root / "config" / "etf_universe.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            from utils.universe_helper import get_universe_symbols

            symbols = get_universe_symbols(cfg, include_benchmark=False) or []
            symbols = [s for s in symbols if isinstance(s, str) and s.strip()]
            if symbols:
                return symbols
        except Exception:
            # fallthrough
            pass
    return []


def _table_columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    cols = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    # pragma: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in cols}


def _chunked(it: Iterable, n: int):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def compute_universe_wide_gaps(
    conn: duckdb.DuckDBPyConnection,
    symbols: list[str],
    venue: str,
) -> tuple[str | None, list[str]]:
    if not symbols:
        return None, []

    placeholders = ",".join(["?"] * len(symbols))

    max_md_date = conn.execute(
        f"SELECT MAX(date) FROM market_data WHERE symbol IN ({placeholders})",
        symbols,
    ).fetchone()[0]

    if max_md_date is None:
        return None, []

    rows = conn.execute(
        f"""
        WITH open_days AS (
            SELECT date
            FROM trading_calendar
            WHERE venue = ?
              AND is_open = TRUE
              AND date <= ?
        ),
        md_any AS (
            SELECT DISTINCT date
            FROM market_data
            WHERE symbol IN ({placeholders})
        )
        SELECT od.date
        FROM open_days od
        LEFT JOIN md_any md ON md.date = od.date
        WHERE md.date IS NULL
        ORDER BY od.date
        """,
        [venue, max_md_date] + symbols,
    ).fetchall()

    gap_dates = [str(r[0]) for r in rows]
    return str(max_md_date), gap_dates


def apply_flags(
    conn: duckdb.DuckDBPyConnection,
    venue: str,
    gap_dates: list[str],
) -> int:
    cols = _table_columns(conn, "trading_calendar")

    set_parts = ["is_open = FALSE"]
    if "quality_flag" in cols:
        set_parts.append("quality_flag = 'large_gap'")
    if "reason" in cols:
        set_parts.append("reason = 'universe_wide_no_market_data'")

    set_sql = ", ".join(set_parts)

    applied = 0
    # Update one date at a time: simpler and avoids dialect edge cases.
    for batch in _chunked(gap_dates, 200):
        for d in batch:
            res = conn.execute(
                f"UPDATE trading_calendar SET {set_sql} WHERE venue = ? AND date = ?",
                [venue, d],
            )
            # DuckDB doesn't always expose affected rows reliably; count via follow-up.
            applied += 1

    return applied


def main() -> int:
    root = _bootstrap_paths()

    parser = argparse.ArgumentParser(description="Flag universe-wide calendar gaps as large_gap (safe remediation).")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default: dry-run only).")
    parser.add_argument("--venue", default=os.getenv("ETF_VENUE", "XMIL"), help="Trading venue (default: ETF_VENUE or BIT).")
    parser.add_argument("--db-path", default=None, help="Override DB path (default: data/db/etf_data.duckdb).")
    parser.add_argument("--coverage-threshold", type=float, default=0.8, help="Kept for consistency (not used for universe-wide gaps).")
    args = parser.parse_args()

    # Resolve DB path
    if args.db_path:
        db_path = Path(args.db_path)
    else:
        try:
            from utils.path_manager import get_path_manager

            db_path = get_path_manager().db_path
        except Exception:
            db_path = root / "data" / "db" / "etf_data.duckdb"

    if not db_path.exists():
        print(f"❌ DB not found: {db_path}")
        return 2

    conn = duckdb.connect(str(db_path))

    symbols = _load_universe_symbols(root)
    if not symbols:
        # fallback to top 5 '.MI'
        try:
            symbols = [r[0] for r in conn.execute(
                """
                SELECT symbol
                FROM market_data
                WHERE symbol LIKE '%%.MI'
                GROUP BY symbol
                ORDER BY COUNT(DISTINCT date) DESC
                LIMIT 5
                """
            ).fetchall()]
        except Exception:
            symbols = []

    max_md_date, gap_dates = compute_universe_wide_gaps(conn, symbols, args.venue)

    print("FLAG LARGE GAPS (universe-wide)")
    print("=" * 80)
    print(f"DB: {db_path}")
    print(f"Venue: {args.venue}")
    print(f"Universe symbols: {len(symbols)}")
    print(f"Max market_data date (universe): {max_md_date}")
    print(f"Universe-wide gaps found: {len(gap_dates)}")

    if not gap_dates:
        print("✅ Nothing to flag.")
        conn.close()
        return 0

    print("Sample (max 30):")
    for d in gap_dates[:30]:
        print(f"  - {d}")

    if not args.apply:
        print("\nDRY-RUN: no changes applied. Use --apply to flag dates.")
        conn.close()
        return 0

    applied = apply_flags(conn, args.venue, gap_dates)
    conn.close()

    # Minimal audit trail file (best-effort)
    try:
        out_dir = root / "data" / "reports" / "integrity"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"flag_large_gaps_{ts}.json"
        out_path.write_text(
            json.dumps(
                {
                    "db": str(db_path),
                    "venue": args.venue,
                    "max_md_date": max_md_date,
                    "gap_count": len(gap_dates),
                    "gap_dates": gap_dates,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"\nReport saved: {out_path}")
    except Exception:
        pass

    print(f"\n✅ Flagged dates attempted: {applied} (see report for the exact list)")
    print("Tip: if you backfill market_data later, you can reopen dates by setting is_open=TRUE (heal).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
