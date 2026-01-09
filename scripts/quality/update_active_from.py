#!/usr/bin/env python3
"""Update active_from in etf_universe.json based on market_data coverage.

Razionale
---------
Se durante l'ingest si tenta sempre una finestra ampia (es. dal 2010),
è utile registrare per ogni simbolo la prima data effettivamente disponibile
nel DB (listing/inception o prima osservazione). Questo evita di considerare
come "missing" giorni precedenti alla nascita del titolo (denominatore dinamico
in operability_gate / sanity_check).

Uso
---
py scripts/quality/update_active_from.py --apply

Opzioni
- --start-floor YYYY-MM-DD: se MIN(date) è precedente, si clampa al floor
  (default: config.initial_start_date o 2010-01-01)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from scripts.utils.path_manager import get_path_manager


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except Exception:
        return None


def _today_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iter_universe_entries(cfg: dict):
    univ = cfg.get("universe")
    if isinstance(univ, dict):
        for group_name, entries in univ.items():
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and e.get("symbol"):
                        yield group_name, e
    # legacy fallback
    for key in ("symbols", "benchmark"):
        entries = cfg.get(key)
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict) and e.get("symbol"):
                    yield key, e


def main():
    ap = argparse.ArgumentParser(description="Update active_from in etf_universe.json based on DB")
    ap.add_argument("--apply", action="store_true", help="Scrive le modifiche su config/etf_universe.json")
    ap.add_argument("--start-floor", type=str, default=None, help="Clamp minimo per active_from (YYYY-MM-DD)")
    args = ap.parse_args()

    pm = get_path_manager()
    cfg_path = pm.etf_universe_path
    db_path = pm.db_path

    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))

    floor = _parse_date(args.start_floor) or _parse_date(cfg.get("initial_start_date")) or date(2010, 1, 1)

    con = duckdb.connect(str(db_path), read_only=False)

    updates = []
    symbols = []
    universe = cfg.get("universe", {})
    if isinstance(universe, dict):
        for group_name, entries in universe.items():
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, dict) and item.get("symbol"):
                        symbols.append(item["symbol"])
    # Fallback a vecchio schema
    if not symbols:
        symbols = cfg.get("symbols") or cfg.get("universe") or []
        if isinstance(symbols, dict):
            symbols = list(symbols.keys())

    for s in symbols:
        try:
            min_d = con.execute("SELECT MIN(date) FROM market_data WHERE symbol = ?", [s]).fetchone()[0]
        except Exception:
            min_d = None

        old = None
        for group, entry in _iter_universe_entries(cfg):
            if entry.get("symbol") == s:
                old = entry.get("active_from")
                break

        if min_d is None:
            updates.append({"symbol": s, "group": None, "old": old, "new": old, "note": "no market_data"})
            continue

        if isinstance(min_d, datetime):
            min_d = min_d.date()

        new_d = max(min_d, floor)
        new_s = new_d.isoformat()

        updates.append({"symbol": s, "group": None, "old": old, "new": new_s, "min_date": str(min_d), "floor": floor.isoformat()})
        for group, entry in _iter_universe_entries(cfg):
            if entry.get("symbol") == s:
                entry["active_from"] = new_s
                break

    con.close()

    stamp = _today_stamp()
    out_dir = pm.reports_dir / "integrity"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "db": str(db_path),
        "config": str(cfg_path),
        "floor": floor.isoformat(),
        "updates": updates,
    }

    json_path = out_dir / f"active_from_update_{stamp}.json"
    md_path = out_dir / f"active_from_update_{stamp}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    # markdown summary
    changed = [u for u in updates if u.get("old") != u.get("new")]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# active_from update\n\n")
        f.write(f"DB: `{db_path}`\n\n")
        f.write(f"Config: `{cfg_path}`\n\n")
        f.write(f"Floor: `{floor.isoformat()}`\n\n")
        f.write(f"Total symbols: {len(updates)}\n\n")
        f.write(f"Changed: {len(changed)}\n\n")
        if changed:
            f.write("| symbol | group | old | new | min_date |\n")
            f.write("|---|---|---|---|---|\n")
            for u in changed:
                f.write(f"| {u['symbol']} | {u['group']} | {u.get('old')} | {u.get('new')} | {u.get('min_date')} |\n")

    if args.apply:
        Path(cfg_path).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Applied. Updated config: {cfg_path}")
    else:
        print("DRY-RUN: no changes applied. Use --apply to write config.")

    print("Report saved:")
    print(f"  {json_path}")
    print(f"  {md_path}")


if __name__ == "__main__":
    main()
