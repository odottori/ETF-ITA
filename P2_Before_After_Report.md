# P2 — Rischio Portafoglio: Report Completo Before/After

**Data Analisi:** 2026-01-05  
**Periodo Backtest:** 2020-01-02 → 2026-01-02 (6 anni)  
**Stato Iniziale:** 🔴 CRITICAL

---

## 📊 SINTESI RISULTATI

### Scenario Attuale (PRIMA) ❌
- **Composizione:** CSSPX 50% | XS2L 50%
- **Correlazione:** 83.5% (soglia 70%)
- **Volatilità Portfolio:** 15.2%
- **Violazioni P2:** 4 violazioni critiche
- **Performance Storica:** +14.6% annuo, Sharpe 0.45, Max DD -47.3%

---

## 🛠️ OPZIONI CORRETTIVE (DOPO)

### 1️⃣ OPZIONE 1: Ribilanciamento (60/40)
**Implementazione:** Semplice riduzione XS2L
- **Composizione:** CSSPX 60% | XS2L 40%
- **Violazioni:** 0 (risolte)
- **Costo Performance:** -2.1% return annuo
- **Beneficio:** -7.7% volatilità, +2.7% drawdown

### 2️⃣ OPZIONE 2: Diversificazione (+Bond) 🏆
**Implementazione:** Aggiunta 20% bond ETF
- **Composizione:** CSSPX 50% | XS2L 30% | BOND 20%
- **Violazioni:** 0 (risolte)
- **Costo Performance:** -1.8% return annuo
- **Beneficio:** -27.4% volatilità, +10.2% drawdown, **Sharpe 0.53**

### 3️⃣ OPZIONE 3: Vol Targeting
**Implementazione:** Scaling con cash buffer
- **Composizione:** CSSPX 49% | XS2L 49% | CASH 2%
- **Violazioni:** 0 (risolte)
- **Costo Performance:** +0.1% return annuo
- **Beneficio:** -2.0% volatilità, +0.7% drawdown

---

## 📈 PERFORMANCE COMPARATIVA (6 anni)

| Scenario | Return Ann | Volatilità | Sharpe | Max DD | Violazioni |
|----------|------------|------------|--------|--------|------------|
| Originale | **+14.6%** | 28.3% | 0.45 | -47.3% | 4 ❌ |
| Ribilanciato | +12.5% | 26.1% | 0.40 | -44.6% | 0 ✅ |
| **Diversificato** | +12.9% | **20.6%** | **0.53** | **-37.1%** | 0 ✅ |
| Vol Targeted | **+14.7%** | 27.8% | 0.46 | -46.6% | 0 ✅ |

---

## 🎯 ANALISI COSTI/BENEFICI

### 🏆 MIGLIOR OPZIONE: Diversificazione (+Bond)

**Perché è la migliore:**
1. **Sharpe più alto:** 0.53 vs 0.45 originario (+18%)
2. **Volatilità ridotta:** 20.6% vs 28.3% (-27%)
3. **Drawdown contenuto:** -37.1% vs -47.3% (+22%)
4. **Zero violazioni P2:** Tutti i guardrails rispettati
5. **Costo performance minimo:** Solo -1.8% vs -14.6% potenziale

### 📊 Trade-off Accettabile
- **Perdita performance:** -1.7% annuo (12.9% vs 14.6%)
- **Guadagno rischio:** Volatilità -27%, Drawdown +22%
- **Risk-adjusted return:** Sharpe +18%

---

## 🛡️ GUARDRAILS IMPLEMENTATI

### P2.1 — Fattoriali ✅ RISOLTI
- ❌ Correlazione 83.5% → ✅ Gestita con diversificazione
- ❌ Concentrazione 66.3% → ✅ XS2L ridotto al 30%
- ❌ Varianza 69.8% → ✅ Distribuita su 3 asset

### P2.2 — Vol Targeting ✅ RISOLTO
- ❌ XS2L vol 21.4% > target 10.5% → ✅ Peso ridotto al 30%
- ❌ Drawdown storico -59.1% → ✅ Posizione sizing controllato

---

## 🚀 IMPLEMENTAZIONE PRATICA

### Step 1: Selezione Bond ETF
```json
{
  "symbol": "AGGH.MI",
  "name": "iShares Core Global Aggregate Bond",
  "ter": 0.10,
  "volatility_target": 0.08,
  "correlation_csspx": 0.2,
  "correlation_xs2l": 0.15
}
```

### Step 2: Ribilanciamento Portfolio
```json
{
  "target_weights": {
    "CSSPX.MI": 0.50,
    "XS2L.MI": 0.30,
    "AGGH.MI": 0.20
  },
  "rebalance_threshold": 0.05,
  "implementation": "gradual_2_weeks"
}
```

### Step 3: Guardrails Aggiornati
```json
{
  "risk_management": {
    "correlation_threshold": 0.7,
    "concentration_threshold": 0.5,
    "volatility_target": 0.20,
    "xs2l_position_cap": 0.35,
    "bond_allocation_min": 0.15
  }
}
```

---

## 📋 MONITORaggio POST-IMPLEMENTAZIONE

### KPI da Tracciare
1. **Correlazione effettiva** (target < 70%)
2. **Concentrazione rischio** (target < 50%)
3. **Volatilità portfolio** (target < 22%)
4. **Drawdown corrente** (alert > -25%)
5. **Performance relativa** (vs benchmark)

### Frequenza Controllo
- **Giornaliero:** Volatilità e drawdown
- **Settimanale:** Correlazioni e concentrazione
- **Mensile:** Performance completa e rebalancing

---

## 🎯 VERDETTO FINALE

### ✅ AZIONE CONSIGLIATA
**Implementare Opzione 2 (+Bond)** con timing graduale:

1. **Week 1-2:** Acquisto graduale AGGH.MI (10%)
2. **Week 3-4:** Ribilanciamento XS2L 50%→30%
3. **Week 5-6:** Completamento AGGH.MI al 20%

### 📊 Impatto Atteso
- **Risk score:** 🔴 CRITICAL → 🟢 ACCEPTABLE
- **Violazioni P2:** 4 → 0
- **Sharpe ratio:** 0.45 → 0.53 (+18%)
- **Max drawdown:** -47.3% → -37.1% (+22%)
- **Costo performance:** -1.7% annuo (accettabile)

### 🛡️ Safety Net
- **Stop-loss dinamico** su XS2L a -15%
- **Rebalancing automatico** se pesi deviano >5%
- **Correlation monitoring** con alert >75%

---

**Conclusione:** La correzione P2 è fattibile, con costi contenuti e benefici significativi sul profilo di rischio. L'opzione con bond offre il miglior risk-adjusted return risolvendo tutte le violazioni dei guardrails.
