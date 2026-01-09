import json
import duckdb
from pathlib import Path

DB = Path("data/db/etf_data.duckdb")
CFG = Path("config/etf_universe.json")

con = duckdb.connect(str(DB))
u = json.loads(CFG.read_text(encoding="utf-8"))

# attesi: lista simboli nel config (adatta se il tuo schema è diverso)
symbols = u.get("symbols") or u.get("universe") or []
if isinstance(symbols, dict):
    symbols = list(symbols.keys())

out = {}
for s in symbols:
    r = con.execute("SELECT MIN(date) FROM market_data WHERE symbol=?", [s]).fetchone()[0]
    out[s] = str(r) if r else None

# scrive active_from su ciascun simbolo nel config
if isinstance(u.get("symbols"), list):
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

CFG.write_text(json.dumps(u, indent=2), encoding="utf-8")
print("Updated active_from in", CFG)
con.close()
