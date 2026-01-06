# AGENT_RULES — ETF_ITA Smart Retail

## 1. Identità dell’Agente
Tu sei l’agente principale del progetto ETF_ITA. Il tuo compito è implementare, mantenere e migliorare il sistema seguendo rigorosamente i documenti canonici.

## 2. Priorità Assolute
1. **Coerenza con i file canonici 003*.md posizionati nella root** (DIPF, DDCT, TLST)
2. Sicurezza operativa (pre-trade controls, sanity, guardrails)
3. Engineering hygiene (requirements.txt, test coverage, schema coherence)
4. Riproducibilità (Run Package)
5. Fiscalità corretta (zainetto per categoria, DIPF §6.2)
6. Zero ambiguità semantica
7. Organizzazione file (MAI .py nella root)

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
- **scripts/core/**: Moduli production (17 file)
- **scripts/utility/**: Manutenzione dati (2 file)
- **scripts/archive/**: File obsoleti (0 file)
- **tests/**: Suite test
- **scripts/temp/**: File temporanei da pulire