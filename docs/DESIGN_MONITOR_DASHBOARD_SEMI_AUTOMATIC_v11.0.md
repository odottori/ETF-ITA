# DESIGN: Monitor Dashboard & Semi-Automatic Trading System

**Progetto:** ETF Italia Smart Retail  
**Package Target:** v11.0.0 (next major version)  
**Doc Version:** v1.0 — 2026-01-08  
**Stato Documento:** 🟡 DESIGN PROPOSAL  
**Autore:** System Design (consolidamento modello prestazionale)

---

## 0. Executive Summary

### 0.1 Obiettivo
Evolvere il sistema da **BACKTEST-READY + DECISION SUPPORT** a **SEMI-AUTOMATIC TRADING SYSTEM** con:
- Monitor dashboard live per visualizzazione continua stato sistema
- Paper trading per validazione strategia in condizioni reali
- Execution workflow human-in-the-loop per ordini reali
- Alert system per notifiche operative urgenti

### 0.2 Filosofia Operativa
**"Sistema co-pilota, non pilota automatico"**

Il sistema:
- ✅ Analizza mercato continuamente
- ✅ Genera segnali oggettivi
- ✅ Propone ordini con motivazioni
- ✅ Calcola costi e impatto fiscale
- ✅ Monitora guardrails e risk management
- ⏸️ **UMANO decide** se eseguire
- ⏸️ **UMANO esegue** su broker
- ✅ Sistema registra e traccia

### 0.3 Perché Semi-Automatic (Non Full-Automatic)
**Vantaggi controllo umano finale**:
1. Evita errori catastrofici da bug software
2. Permette valutazione contesto non quantificabile (news, eventi)
3. Nessun rischio "flash crash" algoritmico
4. Conformità normativa retail
5. Vantaggio psicologico (disciplina senza ansia)

**Rischi full-automatic**:
- Bug → perdite reali immediate
- Dati errati → ordini sbagliati
- Market conditions estreme → nessun override
- Responsabilità legale

---

## 1. Architettura Sistema

### 1.1 Layer Attuali (v10.8.0 - IMPLEMENTATI)

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: DATA & SIGNALS (IMPLEMENTATO)                      │
├─────────────────────────────────────────────────────────────┤
│ Market Data → Signal Engine → Risk Metrics                  │
│ - ingest_data.py (EOD ingestion)                            │
│ - compute_signals.py (trend/momentum/volatility)            │
│ - risk_metrics vista (window functions)                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Layer 2: STRATEGY & ORDERS (IMPLEMENTATO)                   │
├─────────────────────────────────────────────────────────────┤
│ Signals → Strategy Engine V2 → Orders Plan                  │
│ - strategy_engine_v2.py (TWO-PASS workflow)                 │
│ - portfolio_construction.py (holding period dinamico)       │
│ - Pre-trade controls (cash/position checks)                 │
│ - orders_plan table (decision_path, reason_code)            │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Layer Nuovi (v11.0.0 - DA IMPLEMENTARE)

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: MONITOR & DASHBOARD (DA IMPLEMENTARE)              │
├─────────────────────────────────────────────────────────────┤
│ Orders Plan → Dashboard → Human Decision → Execution Log    │
│ - dashboard_monitor.py (Streamlit web app)                  │
│ - alert_system.py (email/Telegram notifications)            │
│ - execution_logger.py (log ordini eseguiti)                 │
│ - reconciliation.py (broker statement vs ledger)            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Layer 4: EXECUTION BRIDGE (OPZIONALE - FUTURO)              │
├─────────────────────────────────────────────────────────────┤
│ Execution Log → [Broker API] → Trade Confirmation           │
│ - broker_api_client.py (IB TWS API / Degiro API)           │
│ - order_submission.py (submit con conferma umana)           │
│ - trade_confirmation.py (auto-reconciliation)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Componenti Chiave

### 2.1 Monitor Dashboard (Priorità: ALTA)

**Tecnologia**: Streamlit (Python web framework)  
**Deployment**: Localhost (http://localhost:8501)  
**Refresh**: Auto-refresh ogni 5-15 minuti (configurabile)

#### 2.1.1 Sezioni Dashboard

**A. Portfolio Overview**
```
┌────────────────────────────────────────────────────────────┐
│ PORTFOLIO CORRENTE                      Cash: €12,450.00   │
├────────────────────────────────────────────────────────────┤
│ Symbol  │ Qty │ Entry    │ Current  │ P&L    │ Days │ SL  │
│ VWCE.MI │ 150 │ €95.20   │ €97.50   │ +€345  │ 12d  │ -8% │
│ SWDA.MI │ 200 │ €42.10   │ €41.80   │ -€60   │ 5d   │ -8% │
│ MEUD.MI │ 100 │ €28.50   │ €29.10   │ +€60   │ 18d  │ -8% │
└────────────────────────────────────────────────────────────┘
Total P&L: +€345 (+2.1%)
```

**B. Segnali Attivi**
```
┌────────────────────────────────────────────────────────────┐
│ SEGNALI ATTIVI (2026-01-08)                                │
├────────────────────────────────────────────────────────────┤
│ VWCE.MI │ RISK_ON  │ Momentum: 0.72 │ Vol: 12.3% │ ✅     │
│ SWDA.MI │ RISK_OFF │ Momentum: 0.45 │ Vol: 18.1% │ ⚠️     │
│ MEUD.MI │ RISK_ON  │ Momentum: 0.68 │ Vol: 14.2% │ ✅     │
│ AGGH.MI │ RISK_ON  │ Momentum: 0.81 │ Vol: 9.5%  │ ✅     │
└────────────────────────────────────────────────────────────┘
```

**C. Ordini Proposti**
```
┌────────────────────────────────────────────────────────────┐
│ ORDINI PROPOSTI                                            │
├────────────────────────────────────────────────────────────┤
│ [SELL] SWDA.MI │ 200 qty │ €41.80                         │
│ Motivo: RISK_OFF (volatility spike 18.1% > 15%)           │
│ Decision: MANDATORY (guardrail trigger)                    │
│ Costo: €8.36 (commission + slippage)                       │
│ Tax: €0 (loss -€60, zainetto +€60)                        │
│ [Confirm] [Reject] [Defer]                                 │
├────────────────────────────────────────────────────────────┤
│ [BUY] AGGH.MI │ 180 qty │ €55.20                          │
│ Motivo: RISK_ON (momentum 0.81, low vol 9.5%)             │
│ Decision: OPPORTUNISTIC (candidate_score 0.78)             │
│ Costo: €19.87 (commission + slippage)                      │
│ Allocation: €10,000 (80% cash available)                   │
│ [Confirm] [Reject] [Defer]                                 │
└────────────────────────────────────────────────────────────┘
```

**D. Guardrails Status**
```
┌────────────────────────────────────────────────────────────┐
│ GUARDRAILS & RISK MANAGEMENT                               │
├────────────────────────────────────────────────────────────┤
│ SPY Guard:        ✅ SAFE (SPY > SMA200)                   │
│ Portfolio DD:     ✅ SAFE (-3.2% < -15% threshold)         │
│ Volatility Regime: ⚠️ ELEVATED (avg vol 14.8%)            │
│ Max Positions:    ✅ OK (3/5 used)                         │
│ Cash Reserve:     ✅ OK (€12,450 > €5,000 min)            │
└────────────────────────────────────────────────────────────┘
```

**E. Performance Summary**
```
┌────────────────────────────────────────────────────────────┐
│ PERFORMANCE (YTD 2026)                                     │
├────────────────────────────────────────────────────────────┤
│ Gross Return:     +4.2%                                    │
│ Net Return:       +3.1% (after costs & tax)                │
│ Sharpe Ratio:     1.45                                     │
│ Max Drawdown:     -5.8%                                    │
│ Win Rate:         62% (8/13 trades)                        │
│ Avg Hold:         14.2 days                                │
└────────────────────────────────────────────────────────────┘
```

#### 2.1.2 Interazioni Dashboard

**Bottoni Azione**:
- `[Confirm Order]` → Log esecuzione manuale
- `[Reject Order]` → Marca ordine come rifiutato (con motivo)
- `[Defer Order]` → Posticipa decisione (rivaluta domani)
- `[Manual Close]` → Chiusura manuale posizione (emergenza)
- `[Refresh Now]` → Force refresh dati

**Form Log Esecuzione**:
```
┌────────────────────────────────────────────────────────────┐
│ LOG EXECUTION: SELL SWDA.MI 200 qty                       │
├────────────────────────────────────────────────────────────┤
│ Execution Price:  [€41.75]                                │
│ Execution Time:   [2026-01-08 09:15:00]                   │
│ Commission:       [€4.95]                                  │
│ Notes:            [Executed at market open]                │
│                                                            │
│ [Submit] [Cancel]                                          │
└────────────────────────────────────────────────────────────┘
```

---

### 2.2 Paper Trading (Priorità: ALTA)

**Obiettivo**: Validare strategia in condizioni reali senza rischio capitale.

#### 2.2.1 Schema DB Extension

```sql
-- Aggiungi colonne a fiscal_ledger
ALTER TABLE fiscal_ledger ADD COLUMN is_paper BOOLEAN DEFAULT false;
ALTER TABLE fiscal_ledger ADD COLUMN execution_status VARCHAR DEFAULT 'PROPOSED';
-- execution_status: PROPOSED / EXECUTED / REJECTED / DEFERRED

-- Aggiungi colonne a orders_plan
ALTER TABLE orders_plan ADD COLUMN is_paper BOOLEAN DEFAULT false;
ALTER TABLE orders_plan ADD COLUMN execution_status VARCHAR DEFAULT 'PROPOSED';
ALTER TABLE orders_plan ADD COLUMN execution_price DOUBLE;
ALTER TABLE orders_plan ADD COLUMN execution_timestamp TIMESTAMP;
ALTER TABLE orders_plan ADD COLUMN execution_notes TEXT;

-- Nuova tabella: execution_log
CREATE TABLE execution_log (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders_plan(id),
    execution_type VARCHAR NOT NULL, -- PAPER / REAL
    execution_status VARCHAR NOT NULL, -- EXECUTED / REJECTED / DEFERRED
    execution_price DOUBLE,
    execution_timestamp TIMESTAMP,
    execution_commission DOUBLE,
    execution_slippage DOUBLE,
    execution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.2.2 Workflow Paper Trading

**Fase 1: Setup (1 giorno)**
```bash
# Attiva modalità paper trading
py scripts/setup/enable_paper_trading.py --enable

# Configura parametri
{
  "paper_trading_enabled": true,
  "paper_start_date": "2026-01-08",
  "paper_initial_cash": 50000,
  "paper_duration_days": 90
}
```

**Fase 2: Esecuzione (3 mesi)**
```
Sistema → Genera ordini (is_paper=true)
Dashboard → Mostra ordini paper
Umano → Conferma ordini (simulati)
Sistema → Esegue ordini paper (prezzi reali EOD)
Sistema → Aggiorna ledger paper
```

**Fase 3: Validazione (fine 3 mesi)**
```bash
# Report performance paper vs real (se disponibile)
py scripts/reports/paper_trading_report.py --start 2026-01-08 --end 2026-04-08

# Output:
# - Sharpe ratio paper vs benchmark
# - Win rate, avg hold, max DD
# - Confronto costi stimati vs reali
# - Decisione: GO/NO-GO per real trading
```

---

### 2.3 Alert System (Priorità: MEDIA)

**Canali Supportati**:
1. **Email** (SMTP)
2. **Telegram** (Bot API)
3. **Console** (log file)

#### 2.3.1 Trigger Alert

**Alert URGENTI** (notifica immediata):
- Guardrail trigger (SPY guard, portfolio DD > 15%)
- Stop-loss hit su posizione
- RISK_OFF signal su posizione aperta
- Ordine proposto MANDATORY (richiede azione)
- Execution timeout (ordine non eseguito entro X ore)

**Alert INFORMATIVI** (notifica giornaliera):
- Nuovi segnali RISK_ON
- Performance summary giornaliera
- Data quality issues (spike, zombie price)
- Cash reserve sotto soglia warning

#### 2.3.2 Configurazione

```json
{
  "alerts": {
    "email": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "from_email": "etf.ita.system@gmail.com",
      "to_email": "user@example.com",
      "urgent_only": true
    },
    "telegram": {
      "enabled": false,
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID"
    },
    "console": {
      "enabled": true,
      "log_file": "data/logs/alerts.log"
    }
  }
}
```

---

### 2.4 Execution Workflow (Priorità: MEDIA)

#### 2.4.1 Flusso Completo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. GENERAZIONE ORDINE                                       │
├─────────────────────────────────────────────────────────────┤
│ Sistema → Strategy Engine V2 → orders_plan                  │
│ Status: PROPOSED                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. NOTIFICA UMANO                                           │
├─────────────────────────────────────────────────────────────┤
│ Dashboard → Mostra ordine + motivazione                     │
│ Alert → Email/Telegram (se urgente)                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. DECISIONE UMANA                                          │
├─────────────────────────────────────────────────────────────┤
│ Opzioni:                                                    │
│ - [Confirm] → Procedi con esecuzione                        │
│ - [Reject] → Rifiuta ordine (con motivo)                   │
│ - [Defer] → Posticipa decisione                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. ESECUZIONE BROKER (MANUALE)                              │
├─────────────────────────────────────────────────────────────┤
│ Umano → Apre piattaforma broker                             │
│ Umano → Inserisce ordine (market/limit)                     │
│ Broker → Esegue ordine                                      │
│ Umano → Riceve conferma esecuzione                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. LOG ESECUZIONE                                           │
├─────────────────────────────────────────────────────────────┤
│ Dashboard → Form "Log Execution"                            │
│ Umano → Inserisce:                                          │
│   - Execution price (reale)                                 │
│   - Execution timestamp                                     │
│   - Commission (reale)                                      │
│   - Notes                                                   │
│ Sistema → Aggiorna orders_plan (status: EXECUTED)           │
│ Sistema → Aggiorna fiscal_ledger                            │
│ Sistema → Aggiorna execution_log                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. RECONCILIATION (OPZIONALE)                               │
├─────────────────────────────────────────────────────────────┤
│ Umano → Upload broker statement (CSV)                       │
│ Sistema → Parse statement                                   │
│ Sistema → Confronta con execution_log                       │
│ Sistema → Report discrepanze (se presenti)                  │
└─────────────────────────────────────────────────────────────┘
```

#### 2.4.2 Chiusure Manuali (Override)

**Scenario**: Emergenza, news improvvisa, o decisione discrezionale.

**Workflow**:
```
Dashboard → Bottone "Manual Close" su posizione
Form → Motivo chiusura (dropdown + note)
  - Emergency exit
  - News-driven
  - Risk management override
  - Other (specify)
Sistema → Genera SELL order (MANUAL flag)
Umano → Esegue su broker
Umano → Log esecuzione
Sistema → Aggiorna ledger
```

#### 2.4.3 Chiusure Automatiche (Condizioni Break)

**Condizioni già implementate**:
- ✅ Stop-loss hit
- ✅ Trailing stop hit
- ✅ RISK_OFF signal
- ✅ Guardrails trigger
- ✅ Holding period scaduto

**Workflow**:
```
Sistema → Rileva condizione break
Sistema → Genera SELL order (AUTO flag, reason_code)
Sistema → Alert urgente (email/Telegram)
Dashboard → Mostra ordine MANDATORY
Umano → Conferma (o override con defer)
Umano → Esegue su broker
Umano → Log esecuzione
Sistema → Aggiorna ledger
```

---

## 3. Requisiti Tecnici

### 3.1 Dipendenze Nuove

```txt
# Dashboard
streamlit==1.30.0
plotly==5.18.0

# Alert System
python-telegram-bot==20.7
smtplib (built-in)

# Utilities
schedule==1.2.0  # per refresh automatico
watchdog==3.0.0  # per file monitoring
```

### 3.2 Configurazione Sistema

```json
{
  "monitor": {
    "enabled": true,
    "refresh_interval_minutes": 5,
    "port": 8501,
    "auto_start": false
  },
  "paper_trading": {
    "enabled": false,
    "initial_cash": 50000,
    "duration_days": 90
  },
  "alerts": {
    "email": { "enabled": true, "urgent_only": true },
    "telegram": { "enabled": false },
    "console": { "enabled": true }
  },
  "execution": {
    "timeout_hours": 24,
    "require_confirmation": true,
    "allow_manual_close": true
  }
}
```

### 3.3 File Structure

```
scripts/
├── monitor/
│   ├── __init__.py
│   ├── dashboard_monitor.py        # Streamlit dashboard
│   ├── alert_system.py             # Email/Telegram alerts
│   ├── execution_logger.py         # Log esecuzioni
│   └── reconciliation.py           # Broker statement reconciliation
├── paper_trading/
│   ├── __init__.py
│   ├── enable_paper_trading.py     # Setup paper trading
│   ├── paper_execution.py          # Esecuzione ordini paper
│   └── paper_trading_report.py     # Report performance paper
└── broker/ (OPZIONALE - FUTURO)
    ├── __init__.py
    ├── broker_api_client.py        # API client (IB/Degiro)
    ├── order_submission.py         # Submit ordini
    └── trade_confirmation.py       # Auto-reconciliation
```

---

## 4. Roadmap Implementazione

### Fase 1: Monitor Dashboard (2-3 settimane)
**Priorità**: ALTA  
**Effort**: 40-60 ore

**Deliverables**:
- [ ] Dashboard Streamlit con 5 sezioni (Portfolio, Segnali, Ordini, Guardrails, Performance)
- [ ] Refresh automatico ogni 5-15 min
- [ ] Bottoni interattivi (Confirm, Reject, Defer, Manual Close)
- [ ] Form log esecuzione
- [ ] Visualizzazioni grafiche (P&L chart, equity curve)

**Test**:
- [ ] Dashboard accessibile su localhost:8501
- [ ] Refresh automatico funzionante
- [ ] Bottoni azione registrano eventi correttamente
- [ ] Form log esecuzione aggiorna DB

---

### Fase 2: Paper Trading (1-2 settimane)
**Priorità**: ALTA  
**Effort**: 20-30 ore

**Deliverables**:
- [ ] Schema DB extension (is_paper, execution_status)
- [ ] Script enable_paper_trading.py
- [ ] Logica esecuzione ordini paper (paper_execution.py)
- [ ] Report performance paper (paper_trading_report.py)
- [ ] Dashboard flag "PAPER MODE" visibile

**Test**:
- [ ] Ordini paper eseguiti con prezzi reali EOD
- [ ] Ledger paper separato da ledger reale
- [ ] Report paper vs benchmark funzionante
- [ ] Forward testing 3 mesi completato

---

### Fase 3: Alert System (1 settimana)
**Priorità**: MEDIA  
**Effort**: 10-15 ore

**Deliverables**:
- [ ] Email alerts (SMTP)
- [ ] Telegram alerts (Bot API)
- [ ] Console logging
- [ ] Configurazione alert triggers (urgent vs informativo)

**Test**:
- [ ] Email ricevuta per guardrail trigger
- [ ] Telegram message ricevuto per stop-loss hit
- [ ] Log file popolato correttamente
- [ ] No spam (solo alert rilevanti)

---

### Fase 4: Execution Workflow (1 settimana)
**Priorità**: MEDIA  
**Effort**: 10-15 ore

**Deliverables**:
- [ ] Execution logger completo
- [ ] Reconciliation broker statement (CSV parser)
- [ ] Report discrepanze execution
- [ ] Timeout alert per ordini non eseguiti

**Test**:
- [ ] Log esecuzione aggiorna correttamente fiscal_ledger
- [ ] Reconciliation identifica discrepanze
- [ ] Timeout alert funzionante dopo 24h
- [ ] Manual close workflow completo

---

### Fase 5: Broker API (OPZIONALE - FUTURO)
**Priorità**: BASSA  
**Effort**: 40-80 ore (dipende da broker)

**Deliverables**:
- [ ] API client Interactive Brokers (TWS API)
- [ ] Order submission automatico (con conferma umana)
- [ ] Trade confirmation automatica
- [ ] Auto-reconciliation

**Test**:
- [ ] Connessione API broker stabile
- [ ] Order submission funzionante
- [ ] Trade confirmation automatica
- [ ] Reconciliation automatica 100% accurata

---

## 5. Requisiti Operativi

### 5.1 Hardware
- **CPU**: 2+ cores (dashboard + refresh background)
- **RAM**: 4GB+ (Streamlit + DuckDB)
- **Storage**: 10GB+ (DB + logs)
- **Network**: Stabile (per refresh dati + alert)

### 5.2 Software
- **OS**: Windows 10/11
- **Python**: 3.10+
- **Browser**: Chrome/Firefox (per dashboard)
- **Email**: Account SMTP (Gmail, Outlook)
- **Telegram**: Bot token (opzionale)

### 5.3 Operatività
- **Orario monitor**: 08:00-20:00 (orario mercati EU)
- **Refresh interval**: 5-15 min (configurabile)
- **Alert response time**: < 1 ora per urgenti
- **Execution window**: Apertura mercato (09:00-09:30)

---

## 6. Metriche Successo

### 6.1 Performance Sistema
- **Dashboard uptime**: > 99% (durante orario mercati)
- **Refresh latency**: < 30 secondi
- **Alert delivery**: < 1 minuto
- **Execution log accuracy**: 100%

### 6.2 Performance Trading (Paper)
- **Sharpe ratio**: > 1.0 (target)
- **Max drawdown**: < 15%
- **Win rate**: > 55%
- **Avg holding**: 10-20 giorni
- **Cost drag**: < 1% annuo

### 6.3 Operatività
- **Execution rate**: > 90% ordini proposti eseguiti
- **Execution timeliness**: < 24h da proposta
- **Manual overrides**: < 10% ordini
- **Reconciliation accuracy**: 100%

---

## 7. Rischi e Mitigazioni

### 7.1 Rischi Tecnici

**R1: Dashboard crash durante orario mercati**
- **Mitigazione**: Auto-restart script, monitoring uptime, fallback console
- **Impatto**: MEDIO

**R2: Alert non ricevuti (email spam, Telegram down)**
- **Mitigazione**: Multi-channel alerts, console log sempre attivo
- **Impatto**: ALTO

**R3: Dati errati (spike, zombie price) generano ordini sbagliati**
- **Mitigazione**: Data quality gates già implementati, human confirmation obbligatoria
- **Impatto**: BASSO (human-in-the-loop protegge)

**R4: Execution log errato (typo prezzo, timestamp)**
- **Mitigazione**: Reconciliation automatica con broker statement, validation input
- **Impatto**: MEDIO

### 7.2 Rischi Operativi

**R5: Umano non disponibile per eseguire ordine urgente**
- **Mitigazione**: Timeout alert, defer option, priorità ordini MANDATORY
- **Impatto**: MEDIO

**R6: Paper trading non rappresentativo (forward-looking bias)**
- **Mitigazione**: Durata minima 3 mesi, periodi volatili inclusi, no cherry-picking
- **Impatto**: ALTO

**R7: Over-trading (troppi ordini proposti)**
- **Mitigazione**: Holding period dinamico, cost penalty, score thresholds
- **Impatto**: MEDIO

---

## 8. Decisioni Architetturali

### 8.1 Perché Streamlit (vs Flask/Django)
**PRO**:
- ✅ Rapid prototyping (200 righe = dashboard completa)
- ✅ Auto-refresh nativo
- ✅ Componenti interattivi built-in
- ✅ Deploy locale semplice

**CONTRO**:
- ❌ Meno flessibile per UI complesse
- ❌ Performance limitata (ma OK per retail)

**Decisione**: Streamlit per MVP, possibile migrazione Flask se necessario.

### 8.2 Perché Paper Trading Obbligatorio
**Motivazione**: Validare strategia in condizioni reali prima di rischiare capitale.

**Durata minima**: 3 mesi (include almeno 1 periodo volatile).

**Criterio GO/NO-GO**:
- Sharpe > 1.0
- Max DD < 15%
- Win rate > 55%
- Nessun bug critico rilevato

### 8.3 Perché Human-in-the-Loop (Non Full-Auto)
**Motivazione**: Retail serio richiede controllo finale umano.

**Vantaggi**:
- Evita disastri da bug
- Permette override discrezionale
- Conformità normativa
- Vantaggio psicologico

**Trade-off**: Richiede disponibilità umana (ma ordini EOD = flessibilità).

---

## 9. Next Steps

### 9.1 Immediate (Settimana 1-2)
1. [ ] Review e approvazione design document
2. [ ] Setup ambiente sviluppo (Streamlit, dipendenze)
3. [ ] Creazione schema DB extension (is_paper, execution_status)
4. [ ] Prototipo dashboard (sezione Portfolio Overview)

### 9.2 Short-term (Mese 1)
1. [ ] Dashboard completa (5 sezioni)
2. [ ] Paper trading setup
3. [ ] Alert system (email)
4. [ ] Test end-to-end workflow

### 9.3 Medium-term (Mese 2-3)
1. [ ] Forward testing paper (3 mesi)
2. [ ] Execution workflow completo
3. [ ] Reconciliation automatica
4. [ ] Report performance paper vs benchmark

### 9.4 Long-term (Mese 4+)
1. [ ] Decisione GO/NO-GO real trading
2. [ ] Primo ordine reale (small size)
3. [ ] Scaling graduale
4. [ ] (Opzionale) Broker API integration

---

## 10. Conclusioni

### 10.1 Valore Proposto
Sistema semi-automatico che:
- ✅ Elimina emotività (segnali oggettivi)
- ✅ Mantiene controllo umano (decisione finale)
- ✅ Valida strategia (paper trading 3 mesi)
- ✅ Monitora continuamente (dashboard live)
- ✅ Protegge capitale (guardrails + human-in-the-loop)

### 10.2 Differenziazione vs Alternatives
**vs Full-Automatic Bot**:
- ✅ Più sicuro (human override)
- ✅ Più flessibile (contesto non quantificabile)
- ❌ Richiede disponibilità umana

**vs Manual Trading**:
- ✅ Più disciplinato (segnali oggettivi)
- ✅ Più efficiente (calcoli automatici)
- ✅ Più riproducibile (audit trail completo)

### 10.3 Raccomandazione
**PROCEDI con implementazione Fase 1-3** (Monitor Dashboard + Paper Trading + Alert System).

**VALUTA dopo 3 mesi paper trading** se procedere con real trading.

**CONSIDERA Broker API** solo se:
- Paper trading successo (Sharpe > 1.0)
- Real trading manuale funzionante (6+ mesi)
- Volumi giustificano automazione (10+ ordini/settimana)

---

**Fine Documento**
