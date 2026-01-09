# Hotfix 08 (operability gate + calendar partial flag)

## What it fixes
- `operability_gate.py` no longer depends on `load_universe_config` (missing in your tree).
- `CalendarHealing` now supports `flag_partial_date(...)` used for WARNING/ALERT days.
- Adds `quarantine_trade_mismatches.py` to safely move BUY/SELL mismatches into `fiscal_ledger_quarantine`.

## Important safety note
The *FULL* consolidated zip contains `data/db/etf_data.duckdb`. Do **not** overwrite your working DB when upgrading.
Use patch zips for code changes, and keep `data/db/etf_data.duckdb` as your single source of truth.
