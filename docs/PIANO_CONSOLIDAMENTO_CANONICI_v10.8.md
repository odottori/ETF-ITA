# PIANO OPERATIVO DI CONSOLIDAMENTO CANONICI v10.8.0

**Data Analisi**: 2026-01-08  
**Agente**: Principale ETF-ITA  
**Obiettivo**: Consolidare revision corrente canonici `003 v10 - *.md` prima di integrare con canonici evoluti v111

---

## 1. ANALISI STATO ATTUALE CANONICI v10.8.0

### 1.1 Metadati Canonici Correnti

| Documento | Package | Doc Revision | Data | Stato |
|-----------|---------|--------------|------|-------|
| **README.md** | v10.8.0 | r40 | 2026-01-07 | BACKTEST-READY |
| **AGENT_RULES.md** | v10.8 | r38 | 2026-01-07 | PRODUCTION READY |
| **DIPF.md** | v10.8.0 | r40 | 2026-01-07 | BACKTEST-READY |
| **DATADICTIONARY.md** | v10.8.0 | r44 | 2026-01-07 | BACKTEST-READY |
| **TODOLIST.md** | v10.8.0 | r40 | 2026-01-07 | BACKTEST-READY |
| **PROJECT_OVERVIEW.md** | v10.8.0 | r40 | 2026-01-07 | BACKTEST-READY |

### 1.2 Incoerenze Rilevate (CRITICAL)

#### A. **DATADICTIONARY.md** - Revision Drift
- **Doc Revision dichiarata**: r44
- **Altre revision**: r40 (maggioranza), r38 (AGENT_RULES)
- **Problema**: DDCT ha 4 revision di vantaggio rispetto agli altri canonici
- **Impatto**: Potenziale disallineamento schema DB vs documentazione

#### B. **Scripts Organization** - Conteggio Incoerente
- **AGENT_RULES.md** (r38): "**Totale**: 53 file Python organizzati in 15 directory"
- **README.md** (r40): "**Scripts Funzionanti** | **53 file Python** (15 directory)"
- **PROJECT_OVERVIEW.md** (r40): "**Totale**: 53 file Python"
- **Breakdown dettagliato** (AGENT_RULES):
  ```
  setup: 4, data: 3, trading: 5, backtest: 3, quality: 7, risk: 7,
  fiscal: 2, reports: 3, orchestration: 4, utils: 4, maintenance: 3,
  analysis: 6, strategy: 1
  TOTALE = 52 file (NON 53!)
  ```
- **Problema**: Conteggio dichiarato 53, somma reale 52
- **Impatto**: Documentazione non accurata, possibile file mancante o errore conteggio

#### C. **Stato Sistema** - Ambiguità Terminologica
- **README.md**: "**BACKTEST-READY v10.8.0** + **DECISION SUPPORT**"
- **AGENT_RULES.md**: "**PRODUCTION READY v10.8**"
- **DIPF.md**: "**BACKTEST-READY v10.8.0 + DECISION SUPPORT (non autonomous production)**"
- **Problema**: Terminologia mista "PRODUCTION READY" vs "BACKTEST-READY"
- **Impatto**: Ambiguità sullo stato reale del sistema

#### D. **Schema DB** - Conteggio Tabelle
- **README.md**: "**Schema DB** | **19 tabelle** (15 tabelle + 4 viste)"
- **DATADICTIONARY.md**: "**DB Objects (19 tabelle + 4 viste)**" ma poi lista "**Tabelle principali (19):**" includendo le viste
- **Problema**: Confusione tra tabelle fisiche e viste nella lista
- **Impatto**: Schema contract potrebbe essere ambiguo

---

## 2. IMPLEMENTAZIONI RECENTI DA CONSOLIDARE

### 2.1 Feature v10.8.0 Implementate (da verificare)

| Feature | File Principale | Status Dichiarato | Verifica Necessaria |
|---------|----------------|-------------------|---------------------|
| **Backtest Event-Driven** | `backtest_engine.py` | [🟢] VERIFIED | ✅ Test esistenti |
| **Strategy Engine V2** | `strategy_engine_v2.py` | [🟢] VERIFIED | ✅ Test esistenti |
| **Holding Period Dinamico** | `portfolio_construction.py` | [🟢] VERIFIED | ✅ Test esistenti |
| **Pre-Trade Controls** | `execute_orders.py` | [🟢] VERIFIED | ✅ Test esistenti |
| **Fiscal Engine Completo** | `tax_engine.py` | [🟢] VERIFIED | ✅ Test esistenti |
| **Auto-Update Proattivo** | `ingest_data.py` | [🟢] VERIFIED | ⚠️ Verifica freshness check |
| **Market Calendar Intelligente** | `market_calendar.py` | [🟢] VERIFIED | ⚠️ Verifica auto-healing |
| **Schema Coherence** | `schema_contract_gate.py` | [🔴] TODO | ❌ Gate non implementato |

### 2.2 Gap Critici Identificati

#### Gap-1: Schema Contract Gate (TL-5.1)
- **TODOLIST.md**: "[🔴] TODO" per `schema_contract_gate.py`
- **Impatto**: Validazione schema non bloccante, rischio drift
- **Priorità**: **ALTA** (safety-critical)

#### Gap-2: Price Convention Check (TL-2.3)
- **TODOLIST.md**: "[🔴] TODO" per `check_price_convention.py`
- **Impatto**: Nessun gate automatico per convenzione adj_close/close
- **Priorità**: **MEDIA** (già verificato manualmente)

#### Gap-3: Cash-Equivalent Ticker (TL-3.3)
- **TODOLIST.md**: "[🔴] TODO" per feature flag cash_equivalent
- **Impatto**: Feature non implementata (baseline EUR/ACC)
- **Priorità**: **BASSA** (out of scope baseline)

---

## 3. PIANO OPERATIVO DI CONSOLIDAMENTO

### FASE 1: VERIFICA COERENZA INTERNA (PRIORITY: CRITICAL)

#### Step 1.1: Riconciliare Revision Numbers
**Obiettivo**: Allineare tutte le revision a un numero coerente

**Azioni**:
1. Verificare se DATADICTIONARY r44 contiene modifiche reali vs r40
2. Se modifiche sostanziali → aggiornare altri canonici a r44
3. Se modifiche minori → retrocedere DATADICTIONARY a r40
4. Aggiornare campo `Doc Revision` in tutti i canonici

**Output**: Tutti i canonici con revision coerente (r40 o r44)

**Comando Verifica**:
```powershell
# Grep per trovare tutte le revision dichiarate
rg "Doc Revision.*r\d+" --glob "003*.md"
```

---

#### Step 1.2: Correggere Conteggio Scripts
**Obiettivo**: Risolvere discrepanza 52 vs 53 file

**Azioni**:
1. Eseguire conteggio reale file Python in `scripts/`:
   ```powershell
   (Get-ChildItem -Path scripts -Recurse -Filter *.py -Exclude __pycache__).Count
   ```
2. Verificare breakdown per directory:
   ```powershell
   Get-ChildItem -Path scripts -Directory | ForEach-Object {
       $count = (Get-ChildItem -Path $_.FullName -Recurse -Filter *.py).Count
       "$($_.Name): $count"
   }
   ```
3. Aggiornare AGENT_RULES.md con conteggio corretto
4. Verificare coerenza con README.md e PROJECT_OVERVIEW.md

**Output**: Conteggio accurato e verificabile

---

#### Step 1.3: Standardizzare Terminologia Stato Sistema
**Obiettivo**: Eliminare ambiguità "PRODUCTION READY" vs "BACKTEST-READY"

**Decisione Proposta**:
- **Terminologia Standard**: "**BACKTEST-READY v10.8.0 + DECISION SUPPORT**"
- **Rationale**: Sistema è robusto per backtest e decision support, NON autonomous production
- **Gap Production Espliciti**: Manca execution bridge broker, monitoring, disaster recovery

**Azioni**:
1. Aggiornare AGENT_RULES.md: "PRODUCTION READY v10.8" → "BACKTEST-READY v10.8.0"
2. Mantenere coerenza in tutti i canonici
3. Aggiungere sezione "Gap Production" in README.md se mancante

**Output**: Terminologia univoca e realistica

---

#### Step 1.4: Chiarire Schema DB (Tabelle vs Viste)
**Obiettivo**: Eliminare confusione tra tabelle fisiche e viste

**Decisione Proposta**:
- **Totale DB Objects**: 19 (15 tabelle fisiche + 4 viste)
- **Lista Separata**: Tabelle fisiche (1-15) e Viste (16-19)

**Azioni**:
1. Aggiornare DATADICTIONARY.md:
   - Sezione "DD-0.1 Database Objects" con lista separata
   - Tabelle fisiche: 1-15
   - Viste: portfolio_overview, portfolio_summary, execution_prices, risk_metrics
2. Verificare coerenza con schema reale:
   ```powershell
   py -c "import duckdb; conn = duckdb.connect('data/db/etf_data.duckdb'); print(conn.execute('SHOW TABLES').fetchall())"
   ```

**Output**: Schema documentato accuratamente

---

### FASE 2: VERIFICA IMPLEMENTAZIONI (PRIORITY: HIGH)

#### Step 2.1: Validare Feature v10.8.0
**Obiettivo**: Confermare che tutte le feature dichiarate [🟢] VERIFIED siano realmente implementate

**Azioni**:
1. Eseguire test suite completa:
   ```powershell
   py -m pytest -v tests/
   ```
2. Verificare esistenza file dichiarati:
   ```powershell
   # Backtest Engine
   Test-Path scripts/backtest/backtest_engine.py
   
   # Strategy Engine V2
   Test-Path scripts/trading/strategy_engine_v2.py
   
   # Portfolio Construction
   Test-Path scripts/strategy/portfolio_construction.py
   
   # Tax Engine
   Test-Path scripts/fiscal/tax_engine.py
   
   # Schema Contract Gate
   Test-Path scripts/quality/schema_contract_gate.py
   ```
3. Eseguire smoke test per ogni feature critica
4. Aggiornare TODOLIST.md con status reale

**Output**: Status verificato per ogni feature

---

#### Step 2.2: Implementare Gap Critici (se necessario)
**Obiettivo**: Chiudere gap safety-critical prima di consolidamento

**Gap da Implementare**:

##### Gap-1: Schema Contract Gate (CRITICAL)
```powershell
# Se mancante, implementare gate bloccante
py scripts/quality/schema_contract_gate.py --strict
```

**Criterio Accettazione**:
- Exit code != 0 se schema non conforme
- Report dettagliato errori/warnings
- Integrazione in CI/CD pipeline

##### Gap-2: Price Convention Check (MEDIUM)
```powershell
# Se mancante, implementare check automatico
py scripts/quality/check_price_convention.py
```

**Criterio Accettazione**:
- Verifica uso adj_close solo per segnali
- Verifica uso close solo per valorizzazione
- Report violazioni con file:line

**Output**: Gap critici chiusi o documentati come "DEFERRED"

---

### FASE 3: AGGIORNAMENTO CANONICI (PRIORITY: MEDIUM)

#### Step 3.1: Sincronizzare Revision Numbers
**Obiettivo**: Portare tutti i canonici alla stessa revision

**Azioni**:
1. Decidere revision target (r40 o r44)
2. Aggiornare header di ogni canonico:
   ```markdown
   **Doc Revision:** r<TARGET> — 2026-01-08
   ```
3. Aggiungere changelog in fondo a ogni canonico:
   ```markdown
   ## Changelog r<TARGET>
   - Consolidamento post-implementazioni v10.8.0
   - Correzione conteggio scripts (52 file)
   - Standardizzazione terminologia stato sistema
   - Chiarificazione schema DB (15 tabelle + 4 viste)
   ```

**Output**: Tutti i canonici con revision coerente

---

#### Step 3.2: Aggiornare Cross-References
**Obiettivo**: Verificare che tutti i riferimenti incrociati siano corretti

**Azioni**:
1. Verificare riferimenti DIPF → DATADICTIONARY:
   ```powershell
   rg "DD-\d+\.\d+" "003 v10 - DIPF ETF-ITA prj.md"
   ```
2. Verificare riferimenti TODOLIST → DIPF:
   ```powershell
   rg "DIPF §\d+\.\d+" "003 v10 - TODOLIST.md"
   ```
3. Verificare riferimenti README → TODOLIST:
   ```powershell
   rg "EP-\d+" "003 v10 - README.md"
   ```
4. Correggere riferimenti rotti o obsoleti

**Output**: Cross-references verificati e corretti

---

#### Step 3.3: Validare Coerenza Semantica
**Obiettivo**: Verificare che non ci siano contraddizioni tra canonici

**Checklist Coerenza**:
- [ ] Baseline produzione (EUR/ACC) coerente in tutti i canonici
- [ ] Execution model (T+1_OPEN) coerente
- [ ] Cost model (TER + slippage + commission) coerente
- [ ] Fiscal model (26% + zainetto) coerente
- [ ] Schema DB (19 objects) coerente
- [ ] Scripts organization (52-53 file) coerente
- [ ] Stato sistema (BACKTEST-READY) coerente

**Azioni**:
1. Eseguire grep per ogni concetto chiave
2. Verificare definizioni coerenti
3. Correggere discrepanze

**Output**: Canonici semanticamente coerenti

---

### FASE 4: VERIFICA FINALE (PRIORITY: HIGH)

#### Step 4.1: Eseguire Quality Gates
**Obiettivo**: Confermare che il sistema sia in stato consolidato

**Gates da Eseguire**:
```powershell
# Unit/Integration Test Gate
py -m pytest -q

# Data Quality Gate
py scripts/quality/health_check.py

# Risk Gate
py scripts/risk/check_guardrails.py

# Accounting Gate
py scripts/quality/sanity_check.py

# Schema Contract Gate
py -m pytest -q tests/test_schema_validation.py
```

**Criterio Successo**: Tutti i gate passano senza errori

---

#### Step 4.2: Generare Report Consolidamento
**Obiettivo**: Documentare stato post-consolidamento

**Report da Generare**:
1. **Consolidation Report** (`docs/history/CONSOLIDATION_REPORT_v10.8.0.md`):
   - Incoerenze risolte
   - Feature verificate
   - Gap chiusi/deferiti
   - Revision finale canonici
   - Quality gates status

2. **Snapshot Canonici** (`docs/backups/003_v10.8.0_consolidated.zip`):
   - Backup canonici consolidati
   - Timestamp consolidamento
   - Hash verification

**Output**: Documentazione completa consolidamento

---

## 4. CRITERI DI ACCETTAZIONE CONSOLIDAMENTO

### 4.1 Criteri MUST (Bloccanti)
- [ ] **C1**: Tutti i canonici hanno revision coerente (r40 o r44)
- [ ] **C2**: Conteggio scripts accurato e verificabile (52 o 53)
- [ ] **C3**: Terminologia stato sistema univoca (BACKTEST-READY)
- [ ] **C4**: Schema DB documentato accuratamente (15+4)
- [ ] **C5**: Tutti i quality gates passano (pytest, health, guardrails, sanity, schema)
- [ ] **C6**: Cross-references verificati e corretti
- [ ] **C7**: Nessuna contraddizione semantica tra canonici

### 4.2 Criteri SHOULD (Non Bloccanti)
- [ ] **C8**: Gap critici implementati (schema_contract_gate, price_convention_check)
- [ ] **C9**: Consolidation report generato
- [ ] **C10**: Snapshot canonici backuppato

---

## 5. TIMELINE STIMATA

| Fase | Durata Stimata | Dipendenze |
|------|----------------|------------|
| **FASE 1**: Verifica Coerenza | 2-3 ore | Nessuna |
| **FASE 2**: Verifica Implementazioni | 3-4 ore | FASE 1 |
| **FASE 3**: Aggiornamento Canonici | 2-3 ore | FASE 1, FASE 2 |
| **FASE 4**: Verifica Finale | 1-2 ore | FASE 1, FASE 2, FASE 3 |
| **TOTALE** | **8-12 ore** | - |

---

## 6. RISCHI E MITIGAZIONI

### Rischio R1: Revision Drift Durante Consolidamento
**Probabilità**: Media  
**Impatto**: Alto  
**Mitigazione**: Lock canonici durante consolidamento, commit atomico

### Rischio R2: Test Failures Durante Verifica
**Probabilità**: Media  
**Impatto**: Alto  
**Mitigazione**: Rollback a stato pre-consolidamento, fix incrementale

### Rischio R3: Implementazioni Mancanti
**Probabilità**: Bassa  
**Impatto**: Medio  
**Mitigazione**: Documentare gap come "DEFERRED", non bloccare consolidamento

---

## 7. PROSSIMI STEP POST-CONSOLIDAMENTO

Una volta completato il consolidamento v10.8.0:

1. **Integrazione Canonici v111**:
   - Estrarre canonici v111 da `_next version\ETF_ITA_v111.zip`
   - Analizzare delta tra v10.8.0 e v111
   - Preparare piano merge incrementale

2. **Evoluzione Documentazione**:
   - Creare canonici evoluti `004 v11 - *.md`
   - Integrare feature v111 (diversificazione titoli, strategie avanzate)
   - Mantenere backward compatibility con v10.8.0

3. **Validazione Sistema**:
   - Eseguire backtest completo su v10.8.0 consolidato
   - Generare baseline performance per confronto v11.x
   - Documentare KPI reference

---

## 8. DECISIONI DA PRENDERE

### D1: Revision Target (r40 vs r44)
**Opzioni**:
- **Opzione A**: Portare tutti a r40 (retrocedere DATADICTIONARY)
- **Opzione B**: Portare tutti a r44 (aggiornare altri canonici)
- **Opzione C**: Mantenere r44 solo per DATADICTIONARY (giustificare)

**Raccomandazione**: **Opzione B** (r44 per tutti) - DATADICTIONARY ha modifiche sostanziali schema

---

### D2: Conteggio Scripts (52 vs 53)
**Opzioni**:
- **Opzione A**: Conteggio reale 52, aggiornare documentazione
- **Opzione B**: Trovare file mancante, confermare 53
- **Opzione C**: Ricontare includendo/escludendo `__init__.py`

**Raccomandazione**: **Opzione A** (verificare conteggio reale, aggiornare doc)

---

### D3: Gap Critici (Implementare vs Defer)
**Opzioni**:
- **Opzione A**: Implementare tutti i gap [🔴] TODO prima di consolidare
- **Opzione B**: Implementare solo gap safety-critical (schema_contract_gate)
- **Opzione C**: Documentare tutti i gap come "DEFERRED", consolidare as-is

**Raccomandazione**: **Opzione B** (implementare solo safety-critical)

---

## 9. APPROVAZIONE PIANO

**Piano Preparato Da**: Agente Principale ETF-ITA  
**Data Preparazione**: 2026-01-08  
**Versione Piano**: 1.0  

**Approvazione Richiesta Per**:
- [ ] Decisione D1 (Revision Target)
- [ ] Decisione D2 (Conteggio Scripts)
- [ ] Decisione D3 (Gap Critici)
- [ ] Avvio FASE 1 (Verifica Coerenza)

---

**NOTA FINALE**: Questo piano è conservativo e metodico. Privilegia accuratezza e verificabilità su velocità. Il consolidamento è prerequisito essenziale per integrare canonici v111 senza introdurre ulteriori incoerenze.
