# PROJECT_OVERVIEW — ETF_ITA Smart Retail (v10.7.0)

## 1. Missione del Progetto
Costruire un sistema EOD “smart retail” per residenti italiani, focalizzato su:
- affidabilità operativa (audit, sanity, guardrails)
- realismo fiscale (PMC, tassazione 26%, zainetto)
- reporting netto e riproducibile (Run Package)
- disciplina decisionale (Signal Engine oggettivo)

## 2. Architettura
- DB: DuckDB (`data/etf_data.duckdb`)
- Runtime: Python 3.10+
- Storage: Parquet + Run Package
- OS: Windows
- Execution Model: T+1_OPEN (default)
- Cost Model: TER drag, slippage dinamico, commissioni realistiche
- Fiscal Model: Italia (OICR_ETF baseline)

## 3. Documenti Canonici
- DIPF ProjectDoc
- DDCT DataDictionary
- TLST ToDoList
- README operativo
- SPECIFICHE OPERATIVE

## 4. Requisiti Funzionali
- RF-01: ingestione dati EOD con audit
- RF-02: health check completo
- RF-03: signal engine oggettivo
- RF-04: guardrails e risk management
- RF-05: strategy engine con dry-run
- RF-06: ledger fiscale con PMC
- RF-07: Run Package serializzato
- RF-08: stress test Monte Carlo
- RF-09: sanity check bloccante
- RF-10: session manager ordinale
- RF-11: benchmark after-tax coerente
- RF-12: EUR/ACC gate
- RF-13: zombie price exclusion
- RF-14: spike detection per simbolo
- RF-15: cash interest mensile
- RF-16: journaling forecast/postcast
- RF-17: emotional gap (se attivo)
- RF-18: tax-friction aware inertia (se attivo)

## 5. Requisiti Non Funzionali
- RNF-01: riproducibilità totale
- RNF-02: determinismo a parità di input
- RNF-03: performance retail-grade
- RNF-04: coerenza fiscale
- RNF-05: auditabilità completa
- RNF-06: robustezza contro dati errati
- RNF-07: documentazione auto-consistente

## 6. Regole di Sviluppo
Ogni modifica deve includere:
- test unitari
- test integrazione
- aggiornamento snapshot
- lint/format
- aggiornamento documentazione

## 7. Output Obbligatori
- manifest.json
- kpi.json
- summary.md
- orders.json
- audit ingestione
- stress test
- sanity check