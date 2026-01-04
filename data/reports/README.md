# 📊 Performance Reports - ETF Italia Project v10

## 📁 Struttura Reports

```
data/reports/
├── sessions/           # 📊 Report organizzati per sessione di lancio
│   ├── 20260104_164304/  # Session storica (primo file: 16:43:04)
│   │   ├── session_info.json
│   │   ├── health_report.md
│   │   ├── stress_test.json
│   │   ├── stress_test_2.json
│   │   └── automated_test_cycle.json
│   └── 20260104_185248/  # Session test (primo file: 18:52:48)
│       ├── session_info.json
│       ├── health_report.json
│       ├── stress_test.json
│       └── performance_summary.json
└── [future_sessions]/  # Session future
```

## 🎯 Logica di Organizzazione

### 📋 **UNA SESSIONE = UN LANCIO**
- **Nome directory**: Data/ora del **PRIMO** file generato
- **Contenuto**: **TUTTI** i report dello stesso lancio
- **Nomi file**: **SENZA** data/ora (solo tipo report)

### 🔄 **ESEMPIO LANCIO:**
```
Lancio alle 16:43:04 → genera 4 file:
├── stress_test_20260104_164304.json      # PRIMO file (16:43:04)
├── health_report_20260104_164700.md      # Secondo file (16:47:00)
├── stress_test_20260104_172824.json       # Terzo file (17:28:24)
└── automated_test_cycle_20260104_173315.json # Quarto file (17:33:15)

↓ Organizzati in:
data/reports/sessions/20260104_164304/    # Data del PRIMO file
├── session_info.json
├── stress_test.json      # Senza timestamp
├── health_report.md      # Senza timestamp
├── stress_test_2.json    # Senza timestamp
└── automated_test_cycle.json # Senza timestamp
```

## 📋 Report Disponibili

### 🔍 Session Storica (20260104_164304)
- **Session**: `20260104_164304` (primo file: 16:43:04)
- **File**: 4 report dello stesso lancio
- **Contenuto**: Health check, stress test (x2), automated test
- **Status**: COMPLETO ✅

### 🧪 Session Test (20260104_185248)
- **Session**: `20260104_185248` (primo file: 18:52:48)
- **File**: 3 report generati
- **Contenuto**: Health check, stress test, performance summary
- **Status**: TEST ✅

## 🚀 Come Generare Nuovi Report

### 📊 Session Manager (Nuova Struttura)
```powershell
# Crea nuova sessione e aggiungi report
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

## 📅 Session History

| Session | Primo File | Tipo | Status | Reports |
|---------|------------|------|--------|---------|
| 20260104_164304 | 16:43:04 | Storica | ✅ | 4 |
| 20260104_185248 | 18:52:48 | Test | ✅ | 3 |

## 🎯 Accesso Rapido

### 📋 Ultima Sessione
```powershell
# Trova session più recente
$latest = Get-ChildItem data/reports/sessions/* | Sort-Object Name -Descending | Select-Object -First 1
Get-Content $latest/session_info.json
```

### 📊 Report Specifici
```powershell
# Session storica completa
Get-Content data/reports/sessions/20260104_164304/session_info.json

# Health report storico
Get-Content data/reports/sessions/20260104_164304/health_report.md

# Stress test storico
Get-Content data/reports/sessions/20260104_164304/stress_test.json

# Automated test storico
Get-Content data/reports/sessions/20260104_164304/automated_test_cycle.json
```

## 🔄 Migrazione da Vecchia Struttura

### ✅ COMPLETATO:
- **Cancellata**: Directory `data/reports/analysis/`
- **Migrati**: Tutti i report in `data/reports/sessions/`
- **Organizzati**: Per sessione di lancio
- **Rinominati**: Senza timestamp nei nomi file

### 📁 Vecchia Struttura (ELIMINATA):
```
data/reports/analysis/  # ❌ ELIMINATA
├── health_report_20260104_164700.md      # → sessions/20260104_164304/
├── stress_test_20260104_164304.json       # → sessions/20260104_164304/
├── stress_test_20260104_172824.json       # → sessions/20260104_164304/
└── automated_test_cycle_20260104_173315.json # → sessions/20260104_164304/
```

---

*Ultimo aggiornamento: 2026-01-04*
