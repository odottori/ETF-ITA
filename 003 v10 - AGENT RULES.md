# AGENT_RULES — ETF_ITA Smart Retail

**Version**: r38 — 2026-01-07  
**System Status**: PRODUCTION READY v10.8

## 1. Identità dell'Agente
Tu sei l'agente principale del progetto ETF_ITA v10.8. Il tuo compito è implementare, mantenere e migliorare il sistema seguendo rigorosamente i documenti canonici.

## 2. Priorità Assolute
1. **Coerenza con i file canonici 003*.md posizionati nella root** (DIPF, DDCT, TLST, README, PROJECT_OVERVIEW)
2. Sicurezza operativa (pre-trade controls, sanity, guardrails)
3. Engineering hygiene (requirements.txt, test coverage, schema coherence)
4. Riproducibilità (Run Package)
5. Fiscalità corretta (zainetto per categoria, DIPF §6.2)
6. **Backtest realistico** (event-driven, cash management corretto)
7. **Data quality** (freshness check, auto-update, market calendar)
8. Zero ambiguità semantica
9. Organizzazione file (MAI .py nella root)

## 3. Regole di Comportamento
- **REGOLA CRITICA**: MAI creare file .py nella root del progetto
- Tutti i file .py devono essere creati in scripts/core, scripts/utility, scripts/temp o tests/
- Non chiedere conferme per modifiche interne non-breaking.
- Chiedi conferma solo per:
  - nuove dipendenze
  - modifiche architetturali
  - rimozione di codice
- Se esiste un file canonico → seguilo senza chiedere.
- Se manca un dettaglio → proponi 3 opzioni e scegli la più coerente.
- Mantieni coerenza tra codice, test, documentazione e snapshot.
- Documenta decisioni importanti nei documenti canonici appropriati

## 4. Cosa puoi generare automaticamente
- codice Python (scripts/core, scripts/utility)
- test unitari e di integrazione
- aggiornamento snapshot KPI
- aggiornamento Run Package
- documentazione tecnica (README, DIPF, DDCT)
- refactoring coerente con DIPF
- validazione schema DB
- aggiornamento session manager

## 5. Cosa NON puoi fare
- introdurre feature non previste senza approvazione
- ignorare DIPF/DDCT/TLST
- modificare convenzioni canoniche (adj_close/close, EUR/ACC, ecc.)
- **MAI** creare file .py nella root del progetto
- introdurre dipendenze senza requirements.txt aggiornato
- modificare schema DB senza aggiornare DATADICTIONARY

## 6. Standard di Qualità
Ogni modifica deve includere:
- test unitari (solo per modifiche critiche o nuove funzionalità)
- test di integrazione (se rilevanti)
- aggiornamento snapshot (per modifiche KPI)
- verifica lint/format
- aggiornamento documentazione canonica (se necessario)
- documentazione decisioni importanti (se necessario)

## 7. Modalità Operativa
Quando ricevi un comando:
1. interpreta l'intento
2. individua i file canonici rilevanti
3. aggiorna codice + test + snapshot
4. genera documentazione
5. verifica coerenza con DIPF/DDCT/TLST
6. esegui lint/format
7. produci un diff leggibile

## 8. Organizzazione Scripts
- **scripts/core/**: Moduli production (18 file)
- **scripts/utils/**: Utility condivise (market_calendar.py)
- **scripts/maintenance/**: Manutenzione dati (update_market_calendar.py)
- **config/**: Configurazione (etf_universe.json, market_holidays.json)
- **tests/**: Suite test (incluso test_market_calendar_quality.py)
- **scripts/temp/**: File temporanei da pulire

## 9. Feature v10.8
- **Backtest Engine**: EVENT-DRIVEN (day-by-day, SELL→BUY, dynamic cash)
- **Auto-Update**: PROATTIVO (ingest + compute automatico, data freshness check)
- **Market Calendar**: INTELLIGENTE (festività + auto-healing chiusure eccezionali)
- **Multi-Preset**: Run ID distinti, KPI separati per ogni preset
- **Data Quality**: Business days calculation esclude weekend + festività