#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import duckdb


def _qident(name: str) -> str:
    # double-quote identifiers safely for DuckDB
    return '"' + name.replace('"', '""') + '"'


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Migrate trading_calendar rows from one venue to another (schema-aware, standalone)."
    )
    ap.add_argument("--db", default="data/db/etf_data.duckdb", help="Path to DuckDB file")
    ap.add_argument("--from", dest="src", required=True, help="Source venue (e.g. BIT)")
    ap.add_argument("--to", dest="dst", required=True, help="Destination venue (e.g. XMIL)")
    ap.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run)")
    ap.add_argument(
        "--drop-source",
        action="store_true",
        help="After successful migrate, delete rows of source venue (dangerous).",
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    con = duckdb.connect(str(db_path))

    # Ensure table exists
    try:
        cols_info = con.execute("PRAGMA table_info('trading_calendar')").fetchall()
    except Exception as e:
        con.close()
        raise SystemExit(f"Cannot read trading_calendar schema: {e}")

    cols = [r[1] for r in cols_info]
    if "date" not in cols or "venue" not in cols:
        con.close()
        raise SystemExit(f"Unexpected schema: trading_calendar columns={cols}")

    src_rows = con.execute("SELECT COUNT(*) FROM trading_calendar WHERE venue=?", [args.src]).fetchone()[0]
    dst_rows = con.execute("SELECT COUNT(*) FROM trading_calendar WHERE venue=?", [args.dst]).fetchone()[0]

    missing = con.execute(
        """
        SELECT COUNT(*)
        FROM trading_calendar s
        WHERE s.venue = ?
          AND NOT EXISTS (
            SELECT 1 FROM trading_calendar d
            WHERE d.venue = ? AND d.date = s.date
          )
        """,
        [args.src, args.dst],
    ).fetchone()[0]

    print("MIGRATE TRADING CALENDAR VENUE")
    print("=" * 80)
    print(f"DB:   {db_path.resolve()}")
    print(f"From: {args.src} (rows={src_rows})")
    print(f"To:   {args.dst} (rows={dst_rows})")
    print(f"Missing dates to copy: {missing}")

    if not args.apply:
        print("DRY-RUN: nessuna modifica applicata. Usa --apply per migrare.")
        con.close()
        return 0

    if missing == 0:
        print("Nothing to do: destination already contains all dates.")
        if args.drop_source:
            print("Note: --drop-source ignored because nothing was inserted.")
        con.close()
        return 0

    # Build INSERT dynamically to match exact schema
    insert_cols = cols[:]  # keep same order as table schema
    insert_cols_sql = ", ".join(_qident(c) for c in insert_cols)

    select_exprs = []
    for c in insert_cols:
        if c == "venue":
            select_exprs.append("? AS " + _qident("venue"))
        else:
            select_exprs.append("s." + _qident(c))
    select_exprs_sql = ", ".join(select_exprs)

    sql = f"""
    INSERT INTO trading_calendar ({insert_cols_sql})
    SELECT {select_exprs_sql}
    FROM trading_calendar s
    WHERE s.venue = ?
      AND NOT EXISTS (
        SELECT 1 FROM trading_calendar d
        WHERE d.venue = ? AND d.date = s.date
      );
    """

    # params: first '?' is dst, then src venue for WHERE, then dst venue for NOT EXISTS
    con.execute(sql, [args.dst, args.src, args.dst])

    after = con.execute("SELECT COUNT(*) FROM trading_calendar WHERE venue=?", [args.dst]).fetchone()[0]
    inserted = after - dst_rows
    print(f"✅ Applied. Inserted: {inserted}")

    if args.drop_source:
        con.execute("DELETE FROM trading_calendar WHERE venue=?", [args.src])
        remaining_src = con.execute("SELECT COUNT(*) FROM trading_calendar WHERE venue=?", [args.src]).fetchone()[0]
        print(f"🧹 Dropped source venue rows. Remaining {args.src}: {remaining_src}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
