#!/usr/bin/env python3
"""Quarantine BUY/SELL rows that do not have matching market_data.

This is a *safe* remediation: rows are copied into fiscal_ledger_quarantine and
then deleted from fiscal_ledger.

Use cases
- Ledger contains legacy/bugged trades on dates for which market_data does not exist.
- Prevents sanity_check FAIL (future leak and ledger/market mismatch).

Notes
- The script targets ONLY BUY/SELL.
- It does NOT touch non-trade rows (DEPOSIT/INTEREST/...).
- Run with --apply; otherwise it prints a preview.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

# Ensure imports (project_root + scripts/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for p in (PROJECT_ROOT, SCRIPTS_DIR):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from utils.path_manager import get_path_manager


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply changes (otherwise preview)")
    args = ap.parse_args()

    pm = get_path_manager()
    con = duckdb.connect(str(pm.db_path))
    try:
        # Find mismatches
        mism = con.execute(
            """
            SELECT fl.*
            FROM fiscal_ledger fl
            LEFT JOIN market_data md
              ON md.symbol = fl.symbol AND md.date = fl.date
            WHERE fl.type IN ('BUY','SELL')
              AND md.date IS NULL
            ORDER BY fl.date, fl.symbol, fl.id
            """
        ).fetchall()

        if not mism:
            print("✅ No BUY/SELL mismatches found.")
            return 0

        ids = [r[0] for r in mism]  # assumes id is first column
        print("QUARANTINE TRADE MISMATCHES")
        print("=" * 80)
        print(f"DB: {pm.db_path}")
        print(f"Rows to quarantine: {len(ids)}")
        print("Sample (max 15):")
        for r in mism[:15]:
            # id, date, symbol, type, qty, price, run_id, mode ... (schema may include more)
            print("  ", r)

        if not args.apply:
            print("\nDRY-RUN: no changes applied. Re-run with --apply.")
            return 0

        # Create quarantine table with same schema
        con.execute("CREATE TABLE IF NOT EXISTS fiscal_ledger_quarantine AS SELECT * FROM fiscal_ledger WHERE 1=0;")

        id_list = ",".join(map(str, ids))
        # Insert missing rows into quarantine (avoid duplicates by id)
        con.execute(
            f"""
            INSERT INTO fiscal_ledger_quarantine
            SELECT * FROM fiscal_ledger
            WHERE id IN ({id_list})
              AND id NOT IN (SELECT id FROM fiscal_ledger_quarantine)
            """
        )

        con.execute(f"DELETE FROM fiscal_ledger WHERE id IN ({id_list});")

        remaining = con.execute(
            """
            SELECT COUNT(*)
            FROM fiscal_ledger fl
            LEFT JOIN market_data md ON md.symbol = fl.symbol AND md.date = fl.date
            WHERE fl.type IN ('BUY','SELL') AND md.date IS NULL
            """
        ).fetchone()[0]

        max_trade = con.execute("SELECT MAX(date) FROM fiscal_ledger WHERE type IN ('BUY','SELL')").fetchone()[0]
        max_md = con.execute("SELECT MAX(date) FROM market_data").fetchone()[0]

        print("\n✅ Applied.")
        print(f"Remaining BUY/SELL mismatches: {remaining}")
        print(f"Max BUY/SELL ledger date: {max_trade}")
        print(f"Max market_data date: {max_md}")
        return 0

    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
