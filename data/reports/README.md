# 📊 Performance Reports - ETF Italia Project v10

## 📁 Struttura Reports

```
data/reports/
├── analysis/           # Analisi performance e test
│   ├── health_report_*.md
│   ├── stress_test_*.json
│   └── automated_test_cycle_*.json
└── [future_reports]/  # Report futuri (backtest, run packages)
```

## 📋 Report Disponibili

### 🔍 Health Check Report
- **File**: `health_report_20260104_164700.md`
- **Contenuto**: Stato sistema, integrità dati, performance
- **Status**: HEALTHY ✅
- **Data**: 2026-01-04T16:46:59

### 📈 Stress Test Reports
- **File**: `stress_test_20260104_164304.json`
- **File**: `stress_test_20260104_172824.json`
- **Contenuto**: Monte Carlo stress test (1000 simulazioni)
- **Risk Level**: HIGH ⚠️

### 🔬 Automated Test Cycle
- **File**: `automated_test_cycle_20260104_173315.json`
- **Contenuto**: Analisi completa ottimizzazione
- **Volatilità**: CSSPX.MI 17.9%, XS2L.MI 39.8%
- **Max DD**: CSSPX.MI -33.6%, XS2L.MI -59.1%

## 🚀 Come Generare Nuovi Report

### 📊 Performance Report Completo
```powershell
py scripts/core/performance_report_generator.py
```

### 🔍 Health Check
```powershell
py scripts/core/health_check.py
```

### 📈 Stress Test
```powershell
py scripts/core/stress_test.py
```

### 🔬 Automated Test Cycle
```powershell
py scripts/core/automated_test_cycle.py
```

## 📊 Metriche Principali

### 🎯 Performance Systema
- **Sharpe Ratio**: 0.96 (ottimizzato)
- **Issues Integrity**: 75 (85.3% weekend/festivi)
- **Stato Sistema**: COMPLETATO

### 📈 Risk Metrics
- **Max Drawdown CSSPX.MI**: -33.6%
- **Max Drawdown XS2L.MI**: -59.1%
- **Volatilità CSSPX.MI**: 17.9%
- **Volatilità XS2L.MI**: 39.8%

### 🔍 Data Quality
- **CSSPX.MI**: 3,905 record (2010-2026)
- **XS2L.MI**: 2,938 record (2010-2026)
- **^GSPC**: 4,025 record (2010-2026)
- **Issues**: 75 integrity issues

## 📅 Report History

| Report | Data | Tipo | Status |
|--------|------|------|--------|
| Health Check | 2026-01-04 | Sistema | HEALTHY |
| Stress Test | 2026-01-04 | Risk | HIGH |
| Automated Test | 2026-01-04 | Analysis | COMPLETO |

## 🎯 Accesso Rapido

### 📋 Health Report
```powershell
Get-Content data/reports/analysis/health_report_20260104_164700.md
```

### 📈 Stress Test
```powershell
Get-Content data/reports/analysis/stress_test_20260104_172824.json
```

### 🔬 Automated Test
```powershell
Get-Content data/reports/analysis/automated_test_cycle_20260104_173315.json
```

---

*Ultimo aggiornamento: 2026-01-04*
