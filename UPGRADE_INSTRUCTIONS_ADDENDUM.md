# ETF-ITA v10.8.5 – Addendum Runbook (DB + Venue)

## 1) Database path (no fx_alpha)
Per ETF-ITA il DB canonico è:

- `data\db\etf_data.duckdb`

Qualsiasi riferimento a `db\fx_alpha.duckdb` va considerato un refuso (FX-ALPHA progetto diverso).

**Upgrade sicuro**
- Quando estrai ZIP di patch, evita di sovrascrivere `data\db\etf_data.duckdb`.
- Fai sempre un backup:
  - `copy .\data\db\etf_data.duckdb .\data\db\etf_data.BACKUP_yyyymmdd_hhmm.duckdb`

## 2) Venue standard: XMIL (con BIT legacy)
Lo standard da usare nelle query/report è `XMIL`.

Se nel tuo DB storico trovi solo `BIT`, hai due opzioni:

1. **Continuare temporaneamente con BIT** (finché non migri il calendario).
2. **Migrare** il calendario su XMIL e mantenere BIT solo come legacy.

I nuovi script accettano sempre `--venue`.
