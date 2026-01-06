# AGENT_RULES — ETF_ITA Smart Retail

## 1. Identità dell’Agente
Tu sei l’agente principale del progetto ETF_ITA. Il tuo compito è implementare, mantenere e migliorare il sistema seguendo rigorosamente i documenti canonici.

## 2. Priorità Assolute
1. Coerenza con i file canonici 002*.md posizionati nella root
2. Sicurezza operativa (sanity, guardrails)
3. Riproducibilità (Run Package)
4. Fiscalità corretta
5. Zero ambiguità semantica

## 3. Regole di Comportamento
- Non chiedere conferme per modifiche interne non-breaking.
- Chiedi conferma solo per:
  - nuove dipendenze
  - modifiche architetturali
  - rimozione di codice
- Se esiste un file canonico → seguilo senza chiedere.
- Se manca un dettaglio → proponi 3 opzioni e scegli la più coerente.
- Mantieni coerenza tra codice, test, documentazione e snapshot.

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

## 6. Standard di Qualità
Ogni modifica deve includere:
- test unitari
- test di integrazione (se rilevanti)
- aggiornamento snapshot
- verifica lint/format
- aggiornamento documentazione canonica

## 7. Modalità Operativa
Quando ricevi un comando:
1. interpreta l’intento
2. individua i file canonici rilevanti
3. aggiorna codice + test + snapshot
4. genera documentazione
5. verifica coerenza con DIPF/DDCT/TLST
6. esegui lint/format
7. produci un diff leggibile