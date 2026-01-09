#!/usr/bin/env python3
"""DB Integrity Report - ETF Italia Project

Report "chirurgico" su:
- future leak (solo BUY/SELL)
- mismatch BUY/SELL senza market_data (date,symbol)
- calendar gaps (giorni open senza market_data universe-wide), bounded a max market_data date
- righe ledger non-trade (DEPOSIT/INTEREST/...) per diagnosi

Output:
- stampa a console
- salva JSON + Markdown in data/reports/integrity/

Uso (PowerShell):
  py scripts\quality\db_integrity_report.py
  py scripts\quality\db_integrity_report.py --limit 50
"""

from __future__ import annotations

import sys
import os

# Aggiungi scripts/ al PYTHONPATH (per import utils/*)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from datetime import datetime
import argparse

import duckdb

from utils.path_manager import get_path_manager
from utils.universe_helper import get_universe_symbols


# JSON-serialization helpers
def _json_safe(obj):
    # Convert common DuckDB/Python objects to JSON-serializable primitives
    try:
        from datetime import date, datetime
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
    except Exception:
        pass
    # Fallback
    return obj


def _row_jsonable(row):
    # Row may be tuple/list; convert elements that need it
    if row is None:
        return None
    out = []
    for x in list(row):
        out.append(_json_safe(x))
    return out



def _table_exists(conn, table_name: str) -> bool:
    try:
        rows = conn.execute('SHOW TABLES').fetchall()
        tables = {r[0] for r in rows}
        return table_name in tables
    except Exception:
        try:
            conn.execute(f'SELECT 1 FROM {table_name} LIMIT 1')
            return True
        except Exception:
            return False

def _table_columns(conn, table_name: str):
    try:
        cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return {c[1] for c in cols}
    except Exception:
        return set()

def _select_cols(existing_cols, desired):
    return [c for c in desired if c in existing_cols]


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100, help="limit rows for sample listings")
    ap.add_argument("--venue", type=str, default=os.environ.get("ETF_VENUE","XMIL"))
    ap.add_argument("--coverage-threshold", type=float, default=0.8)
    args = ap.parse_args()

    pm = get_path_manager()
    db_path = str(pm.db_path)
    config_path = str(pm.etf_universe_path)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    symbols = get_universe_symbols(config, include_benchmark=False)
    if not symbols:
        print("⚠️ Universe symbols vuoto: fallback a symbols da signals")
    n_symbols = max(1, len(symbols))
    min_required = max(1, int((args.coverage_threshold * n_symbols) + 0.9999))  # ceil

    conn = duckdb.connect(db_path)

    # 1) Dates
    max_market_date = None
    if _table_exists(conn, 'market_data'):
        max_market_date = conn.execute("SELECT MAX(date) FROM market_data").fetchone()[0]
    else:
        print('⚠️ market_data table non presente: max_market_date non disponibile.')
    max_ledger_trade_date = conn.execute("""
        SELECT MAX(date) FROM fiscal_ledger WHERE type IN ('BUY','SELL')
    """).fetchone()[0]

    future_leak = False
    if max_market_date and max_ledger_trade_date and max_ledger_trade_date > max_market_date:
        future_leak = True

    # 2) Non-trade rows
    fl_cols = _table_columns(conn, 'fiscal_ledger')
    non_trade_cols = _select_cols(fl_cols, ['id','date','type','symbol','qty','price','run_id','run_type'])
    non_trade_select = ', '.join(non_trade_cols)
    non_trade = conn.execute(f"""
        SELECT {non_trade_select}
        FROM fiscal_ledger
        WHERE type NOT IN ('BUY','SELL')
        ORDER BY date DESC, id DESC
        LIMIT {args.limit}
    """).fetchall()


    # 3) Mismatch BUY/SELL
    mismatch_cols = _select_cols(fl_cols, ['id','date','symbol','type','qty','price','run_id','run_type'])
    mismatch_select = ', '.join([f'fl.{c}' for c in mismatch_cols])
    mismatch = []
    if _table_exists(conn, 'market_data'):
        mismatch = conn.execute(f"""
            SELECT {mismatch_select}
            FROM fiscal_ledger fl
            LEFT JOIN market_data md
              ON md.symbol = fl.symbol AND md.date = fl.date
            WHERE fl.type IN ('BUY','SELL')
              AND md.date IS NULL
            ORDER BY fl.date DESC, fl.symbol
            LIMIT {args.limit}
        """).fetchall()
    else:
        print('⚠️ market_data table non presente: mismatch BUY/SELL non calcolabile (DB minimale / test).')


    # 4) Calendar gaps universe-wide, bounded to max_market_date
    gaps = []
    if max_market_date and symbols:
        placeholders = ",".join(["?"] * len(symbols))
        gaps_df = conn.execute(f"""
            SELECT tc.date
            FROM trading_calendar tc
            LEFT JOIN (
                SELECT DISTINCT date
                FROM market_data
                WHERE symbol IN ({placeholders})
            ) md ON md.date = tc.date
            WHERE tc.venue = ?
              AND tc.is_open = TRUE
              AND tc.date <= ?
              AND md.date IS NULL
            ORDER BY tc.date
        """, list(symbols) + [args.venue, max_market_date]).df()
        gaps = [str(d) for d in gaps_df["date"].tolist()]

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "db_path": db_path,
        "venue": args.venue,
        "coverage_threshold": args.coverage_threshold,
        "symbols": symbols,
        "max_market_date": str(max_market_date) if max_market_date else None,
        "max_ledger_trade_date": str(max_ledger_trade_date) if max_ledger_trade_date else None,
        "future_leak": future_leak,
        "non_trade_sample": [_row_jsonable(r) for r in non_trade],
        "mismatch_sample": [_row_jsonable(r) for r in mismatch],
        "calendar_gaps_universe_wide_count": len(gaps),
        "calendar_gaps_universe_wide_sample": gaps[:args.limit],
    }

    print("\nDB INTEGRITY REPORT")
    print("=" * 80)
    print(f"DB: {db_path}")
    print(f"Venue: {args.venue}")
    print(f"Coverage threshold: {args.coverage_threshold}  (min_required={min_required} / n_symbols={n_symbols})")
    print(f"Max market_data date: {report['max_market_date']}")
    print(f"Max fiscal_ledger trade date (BUY/SELL): {report['max_ledger_trade_date']}")
    print(f"Future leak (BUY/SELL): {future_leak}")

    print("\nNon-trade ledger sample (DEPOSIT/INTEREST/...)")
    for r in non_trade[:min(args.limit, 20)]:
        print("  ", r)

    print("\nMismatch BUY/SELL sample (ledger without market_data)")
    for r in mismatch[:min(args.limit, 20)]:
        print("  ", r)

    print(f"\nCalendar gaps universe-wide (open days without any universe market_data), bounded to max_market_date: {len(gaps)}")
    for d in gaps[:min(args.limit, 20)]:
        print("  ", d)

    out_dir = Path(pm.root) / 'data' / 'reports' / 'integrity'
    _ensure_dir(out_dir)
    stem = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"db_integrity_report_{stem}.json"
    md_path = out_dir / f"db_integrity_report_{stem}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# DB Integrity Report\n\n")
        f.write(f"- Generated at: {report['generated_at']}\n")
        f.write(f"- DB: `{db_path}`\n")
        f.write(f"- Venue: `{args.venue}`\n")
        f.write(f"- Coverage threshold: `{args.coverage_threshold}`\n")
        f.write(f"- Max market_data date: `{report['max_market_date']}`\n")
        f.write(f"- Max fiscal_ledger trade date: `{report['max_ledger_trade_date']}`\n")
        f.write(f"- Future leak (BUY/SELL): `{future_leak}`\n\n")
        f.write("## Mismatch BUY/SELL sample\n\n")
        for r in mismatch[:args.limit]:
            f.write(f"- {r}\n")
        f.write("\n## Calendar gaps universe-wide sample\n\n")
        for d in gaps[:args.limit]:
            f.write(f"- {d}\n")
        f.write("\n## Non-trade ledger sample\n\n")
        for r in non_trade[:args.limit]:
            f.write(f"- {r}\n")

    print(f"\nReport salvato in:\n  {json_path}\n  {md_path}")

if __name__ == "__main__":
    main()
