#!/usr/bin/env python3
"""Operability Gate

Valuta la copertura dei dati (market_data) sull'universo ETF per
ogni giorno OPEN del trading_calendar.

Policy:
- coverage_ratio >= warn_threshold  => WARNING (operabile su subset, flag DATA_PARTIAL)
- coverage_ratio >= alert_threshold => ALERT (rischio alto, flag DATA_PARTIAL)
- coverage_ratio <  alert_threshold => NOOPERATIONS (giorno NON tradabile, flag NO_OPERATIONS)

Miglioria chiave: denominatore DINAMICO
- per ogni giorno si considerano solo i simboli "attivi" (active_from <= day).

Usage tip:
- esegui dopo ingestion (lookback) con --apply per marcare giorni parziali/non operabili.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

import duckdb

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utils.path_manager import get_path_manager
from scripts.utils.calendar_healing import CalendarHealing
from scripts.utils.universe_helper import (
    load_universe_config,
    get_universe_symbol_meta,
)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _date_to_str(d: object) -> str:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.isoformat()
    if isinstance(d, datetime):
        return d.date().isoformat()
    return str(d)


def resolve_venue(cfg: dict) -> str:
    # Priority: env -> cfg.settings.venue -> cfg.venue -> default
    env_v = os.getenv("ETF_VENUE")
    if env_v:
        return env_v
    if isinstance(cfg.get("settings"), dict) and cfg["settings"].get("venue"):
        return str(cfg["settings"]["venue"])
    if cfg.get("venue"):
        return str(cfg["venue"])
    return "XMIL"


def assess_operability(
    conn: duckdb.DuckDBPyConnection,
    venue: str,
    symbols: List[str],
    active_from: Dict[str, date | None],
    start_date: date,
    end_date: date,
    warn_threshold: float,
    alert_threshold: float,
) -> Tuple[List[dict], dict]:
    """Return (daily_rows, summary)."""

    # bound to max market_data date for universe
    max_md = conn.execute(
        "SELECT MAX(date) FROM market_data WHERE symbol IN (%s)" % ",".join(["?"] * len(symbols)),
        symbols,
    ).fetchone()[0]
    if max_md is None:
        raise RuntimeError("market_data is empty for the configured universe")
    max_md_date = max_md if isinstance(max_md, date) else max_md.date()

    effective_end = min(end_date, max_md_date)

    open_days = conn.execute(
        """
        SELECT date
        FROM trading_calendar
        WHERE venue = ? AND is_open = TRUE AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        [venue, start_date, effective_end],
    ).fetchall()
    open_days = [r[0] if isinstance(r[0], date) else r[0].date() for r in open_days]

    # Fetch market data presence for range (universe only)
    md_rows = conn.execute(
        """
        SELECT date, symbol
        FROM market_data
        WHERE symbol IN (%s) AND date BETWEEN ? AND ?
        """ % ",".join(["?"] * len(symbols)),
        symbols + [start_date, effective_end],
    ).fetchall()

    md_by_date: Dict[date, Set[str]] = {}
    for d, sym in md_rows:
        dd = d if isinstance(d, date) else d.date()
        md_by_date.setdefault(dd, set()).add(sym)

    rows: List[dict] = []
    counts = {"FULL": 0, "WARNING": 0, "ALERT": 0, "NOOPERATIONS": 0, "SKIP": 0}

    for d in open_days:
        active_syms = []
        for s in symbols:
            af = active_from.get(s)
            if af is None:
                # treat missing active_from as always active
                active_syms.append(s)
            else:
                if af <= d:
                    active_syms.append(s)

        denom = len(active_syms)
        if denom == 0:
            counts["SKIP"] += 1
            continue

        have_set = md_by_date.get(d, set())
        have = len([s for s in active_syms if s in have_set])
        missing = [s for s in active_syms if s not in have_set]
        ratio = have / float(denom)

        if have == denom:
            level = "FULL"
        elif ratio >= warn_threshold:
            level = "WARNING"
        elif ratio >= alert_threshold:
            level = "ALERT"
        else:
            level = "NOOPERATIONS"

        counts[level] += 1
        rows.append(
            {
                "date": d,
                "active_count": denom,
                "have": have,
                "missing": missing,
                "ratio": ratio,
                "level": level,
            }
        )

    summary = {
        "venue": venue,
        "start_date": start_date,
        "end_date": end_date,
        "effective_end": effective_end,
        "max_md_date": max_md_date,
        "universe_symbols": symbols,
        "warn_threshold": warn_threshold,
        "alert_threshold": alert_threshold,
        "counts": counts,
        "open_days_checked": len(open_days),
    }
    return rows, summary


def apply_flags(
    cal: CalendarHealing,
    venue: str,
    rows: List[dict],
    warn_threshold: float,
    alert_threshold: float,
) -> None:
    for r in rows:
        d: date = r["date"]
        level = r["level"]
        denom = r["active_count"]
        have = r["have"]
        missing = r["missing"]
        ratio = r["ratio"]

        if level == "FULL":
            cal.heal_date(d, venue)
            continue

        reason = f"coverage={have};active={denom};ratio={ratio:.2f};missing={','.join(missing)}"

        if level in ("WARNING", "ALERT"):
            cal.flag_partial_date(
                d,
                venue=venue,
                coverage=have,
                active_count=denom,
                missing_symbols=missing,
                ratio=ratio,
                reason=reason,
            )
        else:
            cal.flag_date(
                d,
                venue=venue,
                quality_flag="NO_OPERATIONS",
                reason=reason,
            )


def write_reports(pm, rows: List[dict], summary: dict) -> Tuple[Path, Path]:
    out_dir = pm.reports_dir / "integrity"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = out_dir / f"operability_gate_{ts}.json"
    md_path = out_dir / f"operability_gate_{ts}.md"

    json_rows = []
    for r in rows:
        rr = dict(r)
        rr["date"] = _date_to_str(rr["date"])
        rr["missing"] = list(rr["missing"]) if isinstance(rr["missing"], (list, tuple, set)) else rr["missing"]
        json_rows.append(rr)

    payload = {
        "summary": {k: _date_to_str(v) if isinstance(v, (date, datetime)) else v for k, v in summary.items()},
        "rows": json_rows,
    }

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # md
    lines = []
    lines.append("# Operability Gate Report\n")
    lines.append(f"- Venue: {summary['venue']}\n")
    lines.append(f"- Universe symbols: {len(summary['universe_symbols'])}\n")
    lines.append(f"- Date range: {summary['start_date']} -> {summary['effective_end']} (max_md={summary['max_md_date']})\n")
    lines.append(f"- Thresholds: warn>={summary['warn_threshold']} alert>={summary['alert_threshold']}\n")
    lines.append("\n## Counts\n")
    for k, v in summary["counts"].items():
        lines.append(f"- {k}: {v}\n")

    # show top offenders
    degraded = [r for r in rows if r["level"] in ("WARNING", "ALERT", "NOOPERATIONS")]
    degraded_sorted = sorted(degraded, key=lambda x: (x["ratio"], x["date"]))
    lines.append("\n## Worst days (sample)\n")
    for r in degraded_sorted[:20]:
        lines.append(
            f"- {r['date']} level={r['level']} ratio={r['ratio']:.2f} have={r['have']}/{r['active_count']} missing={','.join(r['missing'])}\n"
        )

    md_path.write_text("".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Operability gate (data coverage) with active_from-aware denominator")
    parser.add_argument("--venue", default=None)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--warn-threshold", type=float, default=0.8)
    parser.add_argument("--alert-threshold", type=float, default=0.5)
    parser.add_argument("--apply", action="store_true", help="Apply flags to trading_calendar")

    args = parser.parse_args()

    pm = get_path_manager()
    cfg = load_universe_config(pm.etf_universe_path)

    venue = args.venue or resolve_venue(cfg)

    start_d = _parse_date(args.start_date)
    end_d = _parse_date(args.end_date)

    meta = get_universe_symbol_meta(cfg, include_benchmark=False)
    symbols = [m["symbol"] for m in meta]
    active_from = {m["symbol"]: m.get("active_from") for m in meta}

    conn = duckdb.connect(str(pm.db_path))
    try:
        rows, summary = assess_operability(
            conn,
            venue=venue,
            symbols=symbols,
            active_from=active_from,
            start_date=start_d,
            end_date=end_d,
            warn_threshold=args.warn_threshold,
            alert_threshold=args.alert_threshold,
        )

        print("OPERABILITY GATE")
        print("=" * 80)
        print(f"DB: {pm.db_path}")
        print(f"Venue: {venue}")
        print(f"Universe symbols: {len(symbols)}")
        print(f"Date range: {start_d} -> {summary['effective_end']} (max_md={summary['max_md_date']})")
        print(f"Thresholds: warn>={args.warn_threshold} alert>={args.alert_threshold}")
        print(f"Open days checked: {summary['open_days_checked']}")
        print(
            f"FULL: {summary['counts']['FULL']} | WARNING: {summary['counts']['WARNING']} | ALERT: {summary['counts']['ALERT']} | NOOPERATIONS: {summary['counts']['NOOPERATIONS']}"
        )

        if args.apply:
            cal = CalendarHealing(conn)
            apply_flags(cal, venue, rows, args.warn_threshold, args.alert_threshold)
            print("\n✅ Flags applied.")
        else:
            print("\nDRY-RUN: no changes applied. Use --apply to flag dates.")

        json_path, md_path = write_reports(pm, rows, summary)
        print("\nReport saved:")
        print(f"  {json_path}")
        print(f"  {md_path}")
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
