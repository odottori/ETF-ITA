# Risk Assessment Summary - ETF Italia Project v10
**Data:** 2026-01-05  
**Analisi:** Comprehensive Risk Analysis

---

## ⚠️ RISK LEVEL: HIGH

### 📊 Risk Score: 0.530/1.000

**Fattori di Rischio Principali:**
- 📈 **Correlazione:** 0.821 (molto alta)
- 🌊 **Volatilità:** 26.75% (elevata)
- 📉 **Drawdown:** -59.06% (critico)

---

## 🔍 Analisi Dettagliata

### 1. Correlazione ETF
- **CSSPX.MI - XS2L.MI:** 0.821
- **Data Points:** 3,226 giorni
- **Rischio:** Molto alta correlazione → bassa diversificazione
- **Impatto:** I due ETF si muovono quasi in parallelo

### 2. Volatility Clustering
**CSSPX.MI:**
- HIGH_VOL: 172 giorni (13.4%)
- LOW_VOL: 483 giorni (37.6%)
- NORMAL_VOL: 870 giorni (67.7%)

**XS2L.MI:**
- HIGH_VOL: 133 giorni (10.3%)
- LOW_VOL: 450 giorni (35.0%)
- NORMAL_VOL: 702 giorni (54.6%)

### 3. Performance Portfolio (2020-2026)
- **Return Annuale:** 24.70%
- **Volatilità Annuale:** 26.75%
- **Sharpe Ratio:** 0.924
- **Trading Days:** 1,526

### 4. Drawdown Analysis
**CSSPX.MI:**
- **Max Drawdown:** -33.56%
- **Giorni > -10%:** 312 (20.5%)
- **Giorni > -20%:** 29 (1.9%)
- **Rischio Drawdown:** CRITICAL

**XS2L.MI:**
- **Max Drawdown:** -59.06%
- **Giorni > -10%:** 652 (50.7%)
- **Giorni > -20%:** 408 (31.8%)
- **Rischio Drawdown:** CRITICAL

---

## 🎯 Azioni Immediate Richieste

### 🔴 Correlazione Alta (0.821)
- **Ridurre esposizione** a 50-60% per ETF
- **Considerare diversificazione** per asset class
- **Implementare decorrelation strategy**

### 🔴 Volatilità Elevata (26.7%)
- **Implementare volatility targeting** (15-20% max)
- **Position sizing dinamico** basato su VIX
- **Stop-loss automatici** a -15%

### 🔴 Drawdown Severo (-59%)
- **Implementare trailing stop-loss**
- **Risk-off regime detection**
- **Capital preservation priorità**

---

## 🛡️ Strategia di Risk Mitigation

### 1. Position Sizing
- **Max 50% per ETF**
- **Dynamic adjustment** basato su volatilità
- **Correlation-aware allocation**

### 2. Volatility Management
- **Target:** 15-20% annualizzato
- **Trigger:** Riduzione posizione quando vol > 25%
- **Floor:** 10% volatilità minima

### 3. Stop-Loss Strategy
- **Absolute:** -15%
- **Trailing:** -10%
- **Time-based:** 30 giorni senza recupero

### 4. Rebalancing
- **Frequenza:** Mensile
- **Trigger:** Deviazione > 5%
- **Method:** Mean-variance optimization

### 5. Cash Reserve
- **Allocation:** 10-15%
- **Purpose:** Opportunità e emergenze
- **Reinvestment:** Durante drawdown > 15%

---

## 📊 Risk Matrix

| Fattore | Valore | Rischio | Azione |
|---------|--------|--------|--------|
| Correlazione | 0.821 | HIGH | Diversificazione |
| Volatilità | 26.75% | HIGH | Position sizing |
| Drawdown | -59.06% | CRITICAL | Stop-loss |
| Sharpe | 0.924 | MEDIUM | Monitoraggio |

---

## 🎯 Target di Rischio Ottimale

**Obiettivi a 6 mesi:**
- Correlazione < 0.7 (tramite diversificazione)
- Volatilità < 20% (tramite position sizing)
- Max Drawdown < 25% (tramite stop-loss)
- Sharpe > 1.0 (tramite risk-adjusted returns)

---

## 📄 Report Completo

**File:** `comprehensive_risk_analysis_20260105_091552.json`  
**Location:** `data/reports/`

---

**Conclusione:** Il portfolio presenta un rischio elevato principalmente dovuto alla alta correlazione tra ETF e volatilità elevata. Sono necessarie misure immediate di risk management per proteggere il capitale.
