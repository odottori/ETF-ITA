# Calendar Healing System - ETF_ITA v10.8.2

**Data:** 2026-01-08  
**Versione:** 1.0  
**Status:** DESIGN DOCUMENT  

---

## Executive Summary

Il **Calendar Healing System** è un meccanismo auto-correttivo che gestisce data quality issues (zombie prices, large gaps, spike) attraverso il trading calendar invece di rimuovere dati dal database.

**Principio chiave:** Un giorno con dati problematici viene **marcato come non-trading** nel calendar. Il sistema **tenta periodicamente il recupero** dei dati. Se i dati vengono corretti, il giorno viene **ripristinato automaticamente**.

---

## 1. Problema Risolto

### 1.1 Approccio Precedente (Problematico)

**Rimozione dati dal DB:**
- ❌ Perdita permanente di dati storici
- ❌ Logica duplicata in ogni modulo (compute_signals, backtest, risk_management)
- ❌ Nessun tentativo di recupero
- ❌ Difficile audit trail

**Esempio:**
```python
# Ogni modulo deve gestire zombie
if is_zombie_price(date, symbol):
    skip_this_date()

# Logica duplicata in:
# - compute_signals.py
# - backtest_engine.py
# - enhanced_risk_management.py
# - update_ledger.py
```

### 1.2 Approccio Nuovo (Calendar-Based)

**Flagging nel trading calendar:**
- ✅ Dati preservati nel DB (storia completa)
- ✅ Un solo punto di verità (trading_calendar)
- ✅ Retry automatico con healing
- ✅ Audit trail completo
- ✅ Tutti i moduli già rispettano calendar → zero modifiche

**Esempio:**
```python
# Nessun modulo deve cambiare!
# Tutti già fanno:
if not is_open_trading_day(venue, date):
    skip_this_date()

# Il calendar gestisce tutto
```

---

## 2. Architettura Sistema

### 2.1 Schema Trading Calendar Esteso

```sql
CREATE TABLE trading_calendar (
    venue VARCHAR NOT NULL,
    date DATE NOT NULL,
    is_open BOOLEAN NOT NULL,
    
    -- NUOVE COLONNE HEALING
    quality_flag VARCHAR,           -- 'zombie_price', 'large_gap', 'spike', NULL
    flagged_at TIMESTAMP,           -- Quando è stato flaggato
    flagged_reason VARCHAR,         -- Descrizione dettagliata
    retry_count INTEGER DEFAULT 0,  -- Numero tentativi healing
    last_retry TIMESTAMP,           -- Ultimo tentativo
    healed_at TIMESTAMP,            -- Quando è stato healed (se mai)
    
    PRIMARY KEY (venue, date)
);

-- Indici per performance
CREATE INDEX idx_quality_flag ON trading_calendar(quality_flag) WHERE quality_flag IS NOT NULL;
CREATE INDEX idx_retry_pending ON trading_calendar(last_retry, retry_count) WHERE quality_flag IS NOT NULL;
```

### 2.2 Quality Flags

| Flag | Significato | Retry Strategy | Max Retry |
|------|-------------|----------------|-----------|
| `zombie_price` | Prezzo fermo 3+ giorni, volume=0 | Ogni 7 giorni | 3 |
| `large_gap` | Gap > 5 giorni tra date consecutive | Ogni 3 giorni | 2 |
| `spike` | Spike anomalo rilevato | Ogni 1 giorno | 1 |
| `manual_exclusion` | Escluso manualmente (es. data error noto) | Mai | 0 |
| NULL | Giorno normale | N/A | N/A |

### 2.3 Ciclo di Vita Completo

```
┌─────────────────────────────────────────────────────────────┐
│                    CALENDAR HEALING CYCLE                    │
└─────────────────────────────────────────────────────────────┘

1. DETECT (ingest_data.py o auto_clean_data.py)
   │
   ├─→ Trova zombie price su EIMI.MI 2024-03-15
   │
   ↓
2. FLAG (calendar_healing.py)
   │
   ├─→ UPDATE trading_calendar SET
   │     is_open = FALSE,
   │     quality_flag = 'zombie_price',
   │     flagged_at = NOW(),
   │     flagged_reason = 'Price frozen for 3 days, volume=0'
   │   WHERE venue = 'BIT' AND date = '2024-03-15'
   │
   ↓
3. SKIP (compute_signals.py, backtest_engine.py, ecc.)
   │
   ├─→ Tutti i moduli già saltano giorni con is_open=FALSE
   │   → Zombie automaticamente escluso da calcoli
   │
   ↓
4. RETRY (ingest_data.py - run successivo dopo 7 giorni)
   │
   ├─→ Identifica giorni flaggati da ritentare
   ├─→ Re-fetch dati da yfinance per EIMI.MI 2024-03-15
   │
   ├─→ CASO A: Dati ancora zombie
   │   └─→ UPDATE retry_count = retry_count + 1,
   │         last_retry = NOW()
   │
   └─→ CASO B: Dati ora OK!
       └─→ Procedi a HEAL
   │
   ↓
5. HEAL (calendar_healing.py)
   │
   ├─→ UPDATE trading_calendar SET
   │     is_open = TRUE,
   │     quality_flag = NULL,
   │     healed_at = NOW()
   │   WHERE venue = 'BIT' AND date = '2024-03-15'
   │
   └─→ ✅ Giorno ripristinato, dati utilizzabili
```

---

## 3. Componenti Sistema

### 3.1 Modulo Core: `calendar_healing.py`

**Responsabilità:**
- Flagging giorni problematici
- Logica retry intelligente
- Healing automatico
- Audit trail

**Funzioni principali:**

```python
def flag_date(date, symbol, quality_flag, reason):
    """Marca giorno come problematico"""
    
def should_retry(date, quality_flag, retry_count, last_retry):
    """Decide se ritentare healing"""
    
def attempt_healing(date, symbol, quality_flag):
    """Tenta healing: re-fetch + validazione + unflag"""
    
def heal_date(date, symbol):
    """Ripristina giorno come trading day"""
    
def get_flagged_dates_for_retry():
    """Ritorna giorni da ritentare oggi"""
```

### 3.2 Integrazione `ingest_data.py`

**Estensione logica ingest:**

```python
def ingest_with_healing():
    """Ingest normale + healing automatico"""
    
    # 1. Ingest normale (nuovi dati)
    symbols = get_active_symbols()
    for symbol in symbols:
        fetch_and_store_latest(symbol)
    
    # 2. Healing automatico
    flagged_dates = get_flagged_dates_for_retry()
    
    for date, symbol, flag in flagged_dates:
        print(f"🔄 RETRY HEALING: {symbol} {date} (flag: {flag})")
        
        try:
            # Re-fetch specifico
            data = fetch_specific_date(symbol, date)
            
            # Validazione
            if is_data_valid(data, flag):
                # Update market_data
                update_market_data(symbol, date, data)
                
                # Heal calendar
                heal_date(date, symbol)
                print(f"✅ HEALED: {symbol} {date}")
            else:
                # Ancora problematico
                increment_retry_count(date, symbol)
                print(f"⚠️  STILL FLAGGED: {symbol} {date}")
                
        except Exception as e:
            print(f"❌ RETRY FAILED: {symbol} {date} - {e}")
            increment_retry_count(date, symbol)
```

### 3.3 Aggiornamento `auto_clean_data.py`

**Cambio approccio: Flag invece di Delete**

```python
def auto_clean_with_flagging():
    """Pulizia tramite flagging calendar"""
    
    # 1. Identifica zombie prices
    zombies = detect_zombie_prices()
    
    for zombie in zombies:
        # NON rimuovere dal DB
        # Marca nel calendar
        flag_date(
            date=zombie.date,
            symbol=zombie.symbol,
            quality_flag='zombie_price',
            reason=f'Price frozen for {zombie.days} days, volume=0'
        )
        print(f"🚩 FLAGGED: {zombie.symbol} {zombie.date}")
    
    # 2. Identifica large gaps
    gaps = detect_large_gaps()
    
    for gap in gaps:
        flag_date(
            date=gap.date,
            symbol=gap.symbol,
            quality_flag='large_gap',
            reason=f'Gap of {gap.days} days'
        )
        print(f"🚩 FLAGGED: {gap.symbol} {gap.date}")
    
    # 3. Tenta healing giorni già flaggati
    attempt_healing_all_flagged()
```

---

## 4. Impatto su Altri Moduli

### 4.1 Zero Modifiche Necessarie

**Tutti i moduli già rispettano `is_open` (trading_calendar):**

```python
# compute_signals.py - GIÀ FUNZIONA
query = """
SELECT * FROM market_data md
JOIN trading_calendar tc ON md.date = tc.date
WHERE tc.venue = 'BIT' AND tc.is_open = TRUE  -- Salta automaticamente giorni flaggati
"""

# backtest_engine.py - GIÀ FUNZIONA
for date in trading_dates:
    if not is_open_trading_day('BIT', date):
        continue  -- Salta automaticamente giorni flaggati

# enhanced_risk_management.py - GIÀ FUNZIONA
returns = get_returns(symbol, start_date, end_date)
# get_returns deve filtrare per tc.venue='BIT' AND tc.is_open=TRUE
```

### 4.2 Semplificazioni Ottenute

**PRIMA (logica duplicata):**
```python
# compute_signals.py
if is_zombie_price(date):
    skip()

# backtest_engine.py
if is_zombie_price(date):
    skip()

# risk_management.py
if is_zombie_price(date):
    skip()
```

**DOPO (zero logica):**
```python
# Tutti i moduli:
# Nessuna modifica necessaria!
# Il calendar gestisce tutto
```

---

## 5. Retry Strategy Dettagliata

### 5.1 Zombie Prices

**Caratteristiche:**
- Prezzo fermo per 3+ giorni consecutivi
- Volume = 0
- Spesso errore temporaneo di yfinance

**Retry:**
- Intervallo: 7 giorni
- Max retry: 3
- Dopo 30 giorni: Accetta come dato reale (mercato illiquido)

**Logica:**
```python
def should_retry_zombie(flagged_at, retry_count, last_retry):
    days_since_flag = (today - flagged_at).days
    days_since_retry = (today - last_retry).days if last_retry else 999
    
    # Retry ogni 7 giorni, max 3 volte
    if retry_count >= 3:
        return False  # Accetta come dato reale
    
    if days_since_retry < 7:
        return False  # Troppo presto
    
    if days_since_flag > 30:
        return False  # Troppo vecchio, accetta
    
    return True
```

### 5.2 Large Gaps

**Caratteristiche:**
- Gap > 5 giorni tra date consecutive
- Spesso festività, sospensioni, eventi straordinari
- Possono riempirsi se dati arrivano in ritardo

**Retry:**
- Intervallo: 3 giorni
- Max retry: 2
- Dopo 10 giorni: Accetta come gap reale

**Logica:**
```python
def should_retry_gap(flagged_at, retry_count, last_retry):
    days_since_flag = (today - flagged_at).days
    days_since_retry = (today - last_retry).days if last_retry else 999
    
    # Retry ogni 3 giorni, max 2 volte
    if retry_count >= 2:
        return False  # Accetta come gap reale
    
    if days_since_retry < 3:
        return False  # Troppo presto
    
    if days_since_flag > 10:
        return False  # Troppo vecchio, accetta
    
    return True
```

### 5.3 Spike Anomali

**Caratteristiche:**
- Movimento prezzo > 3 std dev
- Potrebbe essere errore temporaneo o movimento reale

**Retry:**
- Intervallo: 1 giorno
- Max retry: 1
- Dopo 3 giorni: Accetta come movimento reale

**Logica:**
```python
def should_retry_spike(flagged_at, retry_count, last_retry):
    days_since_flag = (today - flagged_at).days
    days_since_retry = (today - last_retry).days if last_retry else 999
    
    # Retry dopo 1 giorno, max 1 volta
    if retry_count >= 1:
        return False  # Accetta come movimento reale
    
    if days_since_retry < 1:
        return False  # Troppo presto
    
    if days_since_flag > 3:
        return False  # Troppo vecchio, accetta
    
    return True
```

---

## 6. Audit Trail e Monitoring

### 6.1 Query Utili

**Giorni attualmente flaggati:**
```sql
SELECT 
    date,
    quality_flag,
    flagged_reason,
    flagged_at,
    retry_count,
    last_retry,
    DATEDIFF('day', flagged_at, CURRENT_DATE) as days_flagged
FROM trading_calendar
WHERE quality_flag IS NOT NULL
ORDER BY flagged_at DESC;
```

**Giorni healed (successi):**
```sql
SELECT 
    date,
    quality_flag,
    flagged_at,
    healed_at,
    DATEDIFF('day', flagged_at, healed_at) as days_to_heal,
    retry_count
FROM trading_calendar
WHERE healed_at IS NOT NULL
ORDER BY healed_at DESC;
```

**Tasso di successo healing:**
```sql
SELECT 
    quality_flag,
    COUNT(*) as total_flagged,
    SUM(CASE WHEN healed_at IS NOT NULL THEN 1 ELSE 0 END) as healed,
    ROUND(100.0 * SUM(CASE WHEN healed_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM trading_calendar
WHERE quality_flag IS NOT NULL
GROUP BY quality_flag;
```

### 6.2 Report Healing

**Generato automaticamente in session:**
```
data/reports/sessions/<timestamp>/10_analysis/calendar_healing_<timestamp>.json
```

**Contenuto:**
```json
{
  "timestamp": "20260108_100000",
  "flagged_dates": {
    "zombie_price": 15,
    "large_gap": 221,
    "spike": 3
  },
  "healing_attempts": {
    "total": 45,
    "successful": 12,
    "failed": 33
  },
  "success_rate": {
    "zombie_price": 0.80,
    "large_gap": 0.05,
    "spike": 0.33
  },
  "oldest_flagged": {
    "date": "2024-01-15",
    "days_flagged": 358,
    "quality_flag": "large_gap"
  }
}
```

---

## 7. Vantaggi Sistema

### 7.1 Semplicità

- ✅ **Un solo punto di verità:** trading_calendar
- ✅ **Zero modifiche ai moduli:** Tutti già rispettano calendar
- ✅ **Logica centralizzata:** calendar_healing.py gestisce tutto

### 7.2 Robustezza

- ✅ **Dati preservati:** Nessuna perdita permanente
- ✅ **Auto-correttivo:** Retry automatico con healing
- ✅ **Fallback intelligente:** Accetta dati reali dopo N retry

### 7.3 Trasparenza

- ✅ **Audit trail completo:** Ogni flag/heal tracciato
- ✅ **Monitoring facile:** Query SQL semplici
- ✅ **Report automatici:** Generati in ogni session

### 7.4 Manutenibilità

- ✅ **Facile estensione:** Aggiungi nuovi quality_flag
- ✅ **Configurabile:** Retry strategy modificabile
- ✅ **Testabile:** Logica isolata in un modulo

---

## 8. Casi d'Uso Pratici

### 8.1 Scenario: Zombie Price Temporaneo

**Giorno 1 (2024-03-15):**
```
yfinance ritorna dati errati per EIMI.MI
→ ingest_data.py rileva zombie price
→ calendar_healing.py flagga giorno:
  - is_open = FALSE
  - quality_flag = 'zombie_price'
  - flagged_at = 2024-03-15
```

**Giorno 8 (2024-03-22):**
```
ingest_data.py tenta healing
→ Re-fetch EIMI.MI 2024-03-15
→ Dati ancora zombie
→ retry_count = 1, last_retry = 2024-03-22
```

**Giorno 15 (2024-03-29):**
```
ingest_data.py tenta healing
→ Re-fetch EIMI.MI 2024-03-15
→ Dati ora OK! (yfinance ha corretto)
→ calendar_healing.py heal:
  - is_open = TRUE
  - quality_flag = NULL
  - healed_at = 2024-03-29
→ ✅ Giorno ripristinato, dati utilizzabili
```

### 8.2 Scenario: Large Gap Reale

**Giorno 1 (2024-09-19):**
```
Regina Elisabetta muore, mercati UK chiusi
→ Gap di 3 giorni su ETF UK
→ calendar_healing.py flagga:
  - quality_flag = 'large_gap'
  - flagged_reason = 'Gap of 3 days'
```

**Giorno 4 (2024-09-22):**
```
ingest_data.py tenta healing
→ Re-fetch dati
→ Gap ancora presente (è reale)
→ retry_count = 1
```

**Giorno 7 (2024-09-25):**
```
ingest_data.py tenta healing
→ Gap ancora presente
→ retry_count = 2 (max raggiunto)
→ Sistema accetta gap come reale
→ Giorno rimane flaggato ma non più retry
```

### 8.3 Scenario: Spike Confermato

**Giorno 1 (2024-10-15):**
```
XS2L.MI spike +15% in un giorno
→ spike_detector.py rileva anomalia
→ calendar_healing.py flagga:
  - quality_flag = 'spike'
  - flagged_reason = 'Price spike +15.2%'
```

**Giorno 2 (2024-10-16):**
```
ingest_data.py tenta healing
→ Re-fetch dati
→ Spike confermato (è movimento reale)
→ calendar_healing.py heal:
  - is_open = TRUE
  - quality_flag = NULL
  - healed_at = 2024-10-16
→ ✅ Spike confermato come reale
```

---

## 9. Implementazione

### 9.1 Migration Script

```sql
-- scripts/setup/migrate_calendar_healing.sql

-- Aggiungi colonne healing
ALTER TABLE trading_calendar ADD COLUMN quality_flag VARCHAR;
ALTER TABLE trading_calendar ADD COLUMN flagged_at TIMESTAMP;
ALTER TABLE trading_calendar ADD COLUMN flagged_reason TEXT;
ALTER TABLE trading_calendar ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE trading_calendar ADD COLUMN last_retry TIMESTAMP;
ALTER TABLE trading_calendar ADD COLUMN healed_at TIMESTAMP;

-- Indici
CREATE INDEX idx_quality_flag ON trading_calendar(quality_flag) 
WHERE quality_flag IS NOT NULL;

CREATE INDEX idx_retry_pending ON trading_calendar(last_retry, retry_count) 
WHERE quality_flag IS NOT NULL;

-- Commenti
COMMENT ON COLUMN trading_calendar.quality_flag IS 
'Data quality issue: zombie_price, large_gap, spike, manual_exclusion, NULL';

COMMENT ON COLUMN trading_calendar.retry_count IS 
'Number of healing attempts';

COMMENT ON COLUMN trading_calendar.healed_at IS 
'When the issue was resolved (if ever)';
```

### 9.2 File da Creare

1. **`scripts/utils/calendar_healing.py`** - Modulo core
2. **`scripts/setup/migrate_calendar_healing.sql`** - Migration schema
3. **`tests/test_calendar_healing.py`** - Test suite
4. **`docs/CALENDAR_HEALING_SYSTEM.md`** - Questa documentazione

### 9.3 File da Modificare

1. **`scripts/data/ingest_data.py`** - Aggiungi healing automatico
2. **`scripts/quality/auto_clean_data.py`** - Usa flagging invece di delete
3. **`scripts/quality/health_check.py`** - Report giorni flaggati

---

## 10. Testing

### 10.1 Test Unitari

```python
# tests/test_calendar_healing.py

def test_flag_date():
    """Test flagging di un giorno"""
    flag_date('2024-03-15', 'EIMI.MI', 'zombie_price', 'Test')
    assert get_quality_flag('2024-03-15') == 'zombie_price'
    assert get_is_open('BIT', '2024-03-15') == False

def test_should_retry_zombie():
    """Test logica retry zombie"""
    # Appena flaggato
    assert should_retry('2024-03-15', 'zombie_price', 0, None) == False
    
    # Dopo 7 giorni
    assert should_retry('2024-03-08', 'zombie_price', 0, None) == True
    
    # Max retry raggiunto
    assert should_retry('2024-03-08', 'zombie_price', 3, None) == False

def test_heal_date():
    """Test healing di un giorno"""
    flag_date('2024-03-15', 'EIMI.MI', 'zombie_price', 'Test')
    heal_date('2024-03-15', 'EIMI.MI')
    assert get_quality_flag('2024-03-15') == None
    assert get_is_open('BIT', '2024-03-15') == True
    assert get_healed_at('2024-03-15') is not None
```

### 10.2 Test Integrazione

```python
def test_full_healing_cycle():
    """Test ciclo completo detect-flag-retry-heal"""
    
    # 1. Detect zombie
    zombies = detect_zombie_prices()
    assert len(zombies) > 0
    
    # 2. Flag
    for zombie in zombies:
        flag_date(zombie.date, zombie.symbol, 'zombie_price', 'Test')
    
    # 3. Verify flagged
    flagged = get_flagged_dates()
    assert len(flagged) == len(zombies)
    
    # 4. Attempt healing (mock data now OK)
    mock_data_fixed()
    healed_count = attempt_healing_all_flagged()
    
    # 5. Verify healed
    assert healed_count == len(zombies)
    flagged_after = get_flagged_dates()
    assert len(flagged_after) == 0
```

---

## 11. Monitoring e Alerting

### 11.1 KPI da Monitorare

| KPI | Target | Alert Threshold |
|-----|--------|-----------------|
| Giorni flaggati attivi | < 50 | > 100 |
| Healing success rate | > 70% | < 50% |
| Giorni flaggati > 30 giorni | < 10 | > 20 |
| Retry falliti consecutivi | < 5 | > 10 |

### 11.2 Alert Automatici

```python
def check_healing_health():
    """Verifica salute sistema healing"""
    
    # Alert 1: Troppi giorni flaggati
    flagged_count = count_flagged_dates()
    if flagged_count > 100:
        alert("⚠️  Troppi giorni flaggati: {flagged_count}")
    
    # Alert 2: Success rate basso
    success_rate = calculate_healing_success_rate()
    if success_rate < 0.5:
        alert("⚠️  Healing success rate basso: {success_rate:.1%}")
    
    # Alert 3: Giorni vecchi non healed
    old_flagged = count_flagged_older_than(30)
    if old_flagged > 20:
        alert("⚠️  {old_flagged} giorni flaggati da >30 giorni")
```

---

## 12. Conclusioni

Il **Calendar Healing System** trasforma la gestione data quality da:
- ❌ Approccio distruttivo (rimuovi dati)
- ❌ Logica duplicata (ogni modulo gestisce)
- ❌ Nessun recupero (perdita permanente)

A:
- ✅ Approccio conservativo (preserva dati)
- ✅ Logica centralizzata (un solo punto)
- ✅ Auto-correttivo (retry + healing)

**Impatto:**
- **Semplicità:** Zero modifiche ai moduli esistenti
- **Robustezza:** Sistema auto-healing con fallback intelligente
- **Trasparenza:** Audit trail completo e monitoring facile
- **Manutenibilità:** Facile estensione e configurazione

**Next Steps:**
1. Implementare migration schema
2. Creare modulo calendar_healing.py
3. Integrare in ingest_data.py
4. Aggiornare auto_clean_data.py
5. Testare ciclo completo
6. Monitorare in produzione

---

**Versione:** 1.0  
**Autore:** ETF_ITA System  
**Data:** 2026-01-08  
**Status:** READY FOR IMPLEMENTATION
