# PROJECT_OVERVIEW — ETF_ITA Smart Retail

## 1. Missione del Progetto
Costruire un sistema EOD "smart retail" per residenti italiani, focalizzato su:
- affidabilità operativa (audit, sanity, guardrails)
- realismo fiscale (PMC, tassazione 26%, zainetto)
- reporting netto e riproducibile (Run Package)
- disciplina decisionale (Signal Engine oggettivo)

## 1.1 Stato Sistema
- **Status**: CANDIDATE PRODUCTION
- **Components**: Core modules, risk management, fiscal engine
- **Test Coverage**: VERIFIED BY sanity_check_v003
- **Strategy Engine**: VERIFIED BY strategy_engine_v003
- **Guardrails**: VERIFIED BY guardrails_v003

### Verification Gates
- **Economic Coherence Gate**: `py scripts/core/sanity_check.py --economic-coherence`
- **Critical Fixes Gate**: `py scripts/core/validate_fixes.py --all`
- **Production Gate**: `py scripts/core/production_readiness_test.py`

## 2. Architettura
- DB: DuckDB (`data/etf_data.duckdb`)
- Runtime: Python 3.10+
- Storage: Parquet + Run Package
- OS: Windows
- Execution Model: T+1_OPEN (default)
- Cost Model: TER drag, slippage dinamico, commissioni realistiche
- Fiscal Model: Italia (OICR_ETF baseline)

## 3. Documenti Canonici
- DIPF ProjectDoc (v003)
- DDCT DataDictionary (v003)
- TLST ToDoList (v003)
- README operativo (v003)
- AGENT_RULES (v003)

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

## 6. Standard Qualità
Ogni modifica deve includere:
- test unitari (sempre, indispensabili per regressioni)
- test integrazione (sempre, previene disastri nel 10% dei casi critici)
- aggiornamento snapshot (solo per modifiche KPI)
- lint/format (sempre - formattazione codice standardizzata)
- controllo aggiornamento documentazione / semaforica + cross reference (sempre, tassativo)

### Quality Gates
- **Unit Test Gate**: `py -m pytest tests/unit/ --cov=scripts/core`
- **Integration Test Gate**: `py -m pytest tests/integration/ --cov=scripts/core`
- **Documentation Gate**: `py scripts/utility/check_canonical_consistency.py`

## 7. Output Obbligatori
- manifest.json
- kpi.json
- summary.md
- orders.json
- audit ingestione
- stress test
- sanity check

## 8. Architettura Scripts
- **scripts/core/**: Moduli production (17 file)
- **scripts/utility/**: Manutenzione dati (2 file)
- **scripts/archive/**: File obsoleti (0 file)
- **tests/**: Suite test
- **scripts/temp/**: File temporanei da pulire

## 9. Organizzazione File
- **REGOLA CRITICA**: MAI creare file .py nella root del progetto
- Tutti i file .py devono essere creati in scripts/core, scripts/utility, scripts/temp o tests/
- La root contiene solo documenti canonici e configurazione
