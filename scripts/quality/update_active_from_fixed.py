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
py scripts/quality/update_active_from.py

Opzioni
- --start-floor YYYY-MM-DD: se MIN(date) è precedente, si clampa al floor
  (default: config.initial_start_date o 2010-01-01)
"""

import json
import duckdb
from pathlib import Path

DB = Path("data/db/etf_data.duckdb")
CFG = Path("config/etf_universe.json")

def main():
    con = duckdb.connect(str(DB))
    u = json.loads(CFG.read_text(encoding="utf-8"))

    # attesi: lista simboli nel config (adatta se il tuo schema è diverso)
    symbols = []
    
    # Estrai simboli dal universe structure
    universe = u.get("universe", {})
    if isinstance(universe, dict):
        for group_name, entries in universe.items():
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, dict) and item.get("symbol"):
                        symbols.append(item["symbol"])
    
    # Fallback a vecchio schema
    if not symbols:
        symbols = u.get("symbols") or u.get("universe") or []
        if isinstance(symbols, dict):
            symbols = list(symbols.keys())

    out = {}
    for s in symbols:
        r = con.execute("SELECT MIN(date) FROM market_data WHERE symbol=?", [s]).fetchone()[0]
        out[s] = str(r) if r else None

    # scrive active_from su ciascun simbolo nel config
    universe = u.get("universe", {})
    if isinstance(universe, dict):
        for group_name, entries in universe.items():
            if isinstance(entries, list):
                for item in entries:
                    sym = item.get("symbol") or item.get("ticker")
                    if sym in out and out[sym]:
                        item["active_from"] = out[sym]
    
    # Fallback a vecchio schema
    elif isinstance(u.get("symbols"), list):
        # lista di dict: [{"symbol": "...", ...}]
        for item in u["symbols"]:
            sym = item.get("symbol") or item.get("ticker")
            if sym in out and out[sym]:
                item["active_from"] = out[sym]
    elif isinstance(u.get("symbols"), dict):
        # dict: {"CSSPX.MI": {...}}
        for sym, meta in u["symbols"].items():
            if sym in out and out[sym]:
                meta["active_from"] = out[sym]

    CFG.write_text(json.dumps(u, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Updated active_from in", CFG)
    con.close()

if __name__ == "__main__":
    main()
