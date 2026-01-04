# 📊 Performance Reports - ETF Italia Project v10

## 📁 Struttura Reports

```
data/reports/
├── analysis/           # [DEPRECATED] Vecchi report (migrati a sessions/)
├── sessions/           # 📊 Nuova struttura con timestamp univoco
│   ├── 20260104_164304/  # Session più vecchia
│   │   ├── session_info.json
│   │   └── stress_test.json
│   ├── 20260104_164700/  # Health check session
│   │   ├── session_info.json
│   │   └── health_report.md
│   ├── 20260104_172824/  # Stress test session
│   │   ├── session_info.json
│   │   └── stress_test.json
│   ├── 20260104_173315/  # Automated test session
│   │   ├── session_info.json
│   │   └── automated_test_cycle.json
│   └── 20260104_183535/  # Session più recente (demo)
│       ├── session_info.json
│       ├── health_report.json
│       ├── stress_test.json
│       └── performance_summary.json
└── [future_sessions]/  # Session future
```

## 📋 Report Disponibili

### 🔍 Health Check Report
- **Session**: `20260104_164700`
- **File**: `health_report.md`
- **Contenuto**: Stato sistema, integrità dati, performance
- **Status**: HEALTHY ✅
- **Data**: 2026-01-04T16:47:00

### 📈 Stress Test Reports
- **Session**: `20260104_164304`
- **File**: `stress_test.json`
- **Contenuto**: Monte Carlo stress test (vecchio)

- **Session**: `20260104_172824`
- **File**: `stress_test.json`
- **Contenuto**: Monte Carlo stress test (recente)
- **Risk Level**: HIGH ⚠️

### 🔬 Automated Test Cycle
- **Session**: `20260104_173315`
- **File**: `automated_test_cycle.json`
- **Contenuto**: Analisi completa ottimizzazione
- **Volatilità**: CSSPX.MI 17.9%, XS2L.MI 39.8%
- **Max DD**: CSSPX.MI -33.6%, XS2L.MI -59.1%

## 🚀 Come Generare Nuovi Report

### 📊 Performance Report Completo
```powershell
# Usa il nuovo session manager
py scripts/core/simple_report_session_manager.py
```

### 🔍 Health Check
```powershell
py scripts/core/health_check.py
# Output: data/reports/sessions/<timestamp>/health_report.json
```

### 📈 Stress Test
```powershell
py scripts/core/stress_test.py
# Output: data/reports/sessions/<timestamp>/stress_test.json
```

### 🔬 Automated Test Cycle
```powershell
py scripts/core/automated_test_cycle.py
# Output: data/reports/sessions/<timestamp>/automated_test_cycle.json
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

| Session | Data | Tipo | Status | Reports |
|---------|------|------|--------|---------|
| 20260104_164304 | 2026-01-04 16:43 | Stress Test | ✅ | 1 |
| 20260104_164700 | 2026-01-04 16:47 | Health Check | ✅ | 1 |
| 20260104_172824 | 2026-01-04 17:28 | Stress Test | ✅ | 1 |
| 20260104_173315 | 2026-01-04 17:33 | Automated Test | ✅ | 1 |
| 20260104_183535 | 2026-01-04 18:35 | Demo | ✅ | 3 |

## 🎯 Accesso Rapido

### 📋 Ultima Sessione
```powershell
# Trova session più recente
$latest = Get-ChildItem data/reports/sessions/* | Sort-Object Name -Descending | Select-Object -First 1
Get-Content $latest/session_info.json
```

### 📊 Report Specifici
```powershell
# Health report più recente
Get-Content data/reports/sessions/20260104_164700/health_report.md

# Stress test più recente
Get-Content data/reports/sessions/20260104_172824/stress_test.json

# Automated test più recente
Get-Content data/reports/sessions/20260104_173315/automated_test_cycle.json
```

## 🔄 Migrazione da Vecchia Struttura

### ✅ COMPLETATO:
- Tutti i report da `data/reports/analysis/` migrati a `data/reports/sessions/`
- Session info creato per ogni report
- Timestamp univoco per ogni sessione
- Metadata completi con file originali

### 📁 Vecchia Struttura (DEPRECATED):
```
data/reports/analysis/
├── health_report_20260104_164700.md      # → sessions/20260104_164700/
├── stress_test_20260104_164304.json       # → sessions/20260104_164304/
├── stress_test_20260104_172824.json       # → sessions/20260104_172824/
└── automated_test_cycle_20260104_173315.json # → sessions/20260104_173315/
```

---

*Ultimo aggiornamento: 2026-01-04*
