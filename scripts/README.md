# Scripts Organization - ETF Italia Project v10

## 📁 Scripts Organization

```
scripts/
├── core/           # Core system scripts (EP-01..EP-10)
├── utility/        # Analysis, testing, and utility scripts
├── archive/        # Temporary implementation scripts
└── advanced/       # [DELETED] Advanced ML and optimization scripts
```

### 🗑️ Advanced Scripts - ARCHIVIATI
Tutti gli advanced scripts sono stati archiviati perché:
- **Over-engineering**: ML non necessario per sistema semplice
- **Duplicazione**: Funzionalità già presenti in core scripts
- **Complessità**: Manutenzione troppo alta per valore aggiunto
- **Dependencies**: sklearn non necessario per produzione

**Scripts archiviati:**
- `adaptive_signal_engine.py` (436 linee) - ML signal engine
- `auto_strategy_optimizer.py` (451 linee) - ML optimizer
- `simple_strategy_optimizer.py` (337 linee) - Simple optimizer
- `master_runner.py` (400 linee) - Orchestrator
- `complete_system_test.py` (395 linee) - System test

**Vedi `scripts/advanced_analysis.md` per analisi dettagliata.**

## 🔧 Core Scripts (25 files)

### EntryPoint Scripts (EP-01..EP-10)
- `setup_db.py` (314 lines) - Database setup
- `load_trading_calendar.py` (178 lines) - Trading calendar
- `ingest_data.py` (304 lines) - Data ingestion
- `compute_signals.py` (305 lines) - Signal engine
- `strategy_engine.py` (259 lines) - Strategy engine
- `backtest_runner.py` (464 lines) - Backtest runner
- `update_ledger.py` (227 lines) - Fiscal ledger

### Risk & Validation Scripts
- `health_check.py` (404 lines) - System health check
- `check_guardrails.py` (244 lines) - Risk guardrails
- `stress_test.py` (201 lines) - Monte Carlo stress test
- `sanity_check.py` (168 lines) - Sanity checks

### Advanced Scripts
- `adaptive_signal_engine.py` (436 lines) - ML-based signal engine
- `auto_strategy_optimizer.py` (451 lines) - Strategy optimizer
- `simple_strategy_optimizer.py` (337 lines) - Simple optimizer
- `master_runner.py` (369 lines) - Master runner
- `complete_system_test.py` (390 lines) - Complete system test

### Utility Scripts
- `fix_all_issues.py` (356 lines) - Data integrity fixer
- `create_alpha_signals.py` (257 lines) - Alpha signals
- `automated_test_cycle.py` (313 lines) - Automated test cycle
- `performance_report_generator.py` (221 lines) - Performance reports

## 📁 Utility Scripts (14 files)

### Analysis Scripts
- `analyze_warning.py` (49 lines) - EP-04 warning analysis
- `analyze_alternative_data.py` (145 lines) - Alternative data analysis
- `analyze_calendar.py` (157 lines) - Calendar analysis
- `analyze_xs2l.py` (161 lines) - XS2L analysis
- `analyze_warning_and_updates.py` (247 lines) - Warning and updates

### Testing Scripts
- `test_conformity.py` (204 lines) - System conformity test
- `test_fallback.py` (18 lines) - Fallback test
- `test_update_routines.py` (225 lines) - Update routines test

### Data Management Scripts
- `extend_historical_data.py` (178 lines) - Historical data extension
- `data_quality_audit.py` (221 lines) - Data quality audit
- `setup_symbol_registry.py` (139 lines) - Symbol registry setup

### Portfolio Scripts
- `create_portfolio_overview_fixed.py` (101 lines) - Portfolio overview
- `create_portfolio_simple.py` (79 lines) - Simple portfolio

### Utility Scripts
- `clear_signals.py` (5 lines) - Clear signals
- `check_issues.py` (7 lines) - Check issues

## 📁 Archive Scripts (10 files)

### Implementation Phase Scripts
- `phase1_implementation.py` (207 lines) - Phase 1 implementation
- `phase2_implementation.py` (241 lines) - Phase 2 implementation
- `phase3_implementation.py` (335 lines) - Phase 3 implementation
- `phase4_implementation.py` (267 lines) - Phase 4 implementation

### Optimization Scripts
- `optimization_implementation.py` (279 lines) - Optimization implementation
- `optimization_summary.py` (177 lines) - Optimization summary

### Final Scripts
- `final_data_assessment.py` (226 lines) - Final data assessment
- `final_implementation_summary.py` (222 lines) - Final implementation summary
- `final_issue_resolution.py` (260 lines) - Final issue resolution
- `final_system_status.py` (217 lines) - Final system status

## 📊 Statistics

### Before Reorganization
- **Total scripts**: 53
- **Total lines**: ~12,000
- **Duplicated scripts**: 4+
- **Temporary scripts**: 10+
- **No organization**: Flat structure

### After Reorganization
- **Total scripts**: 25 (core) + 14 (utility) + 10 (archive) = 49
- **Core scripts**: 25 (essential for production)
- **Utility scripts**: 14 (analysis and testing)
- **Archive scripts**: 10 (temporary implementation)
- **Organized structure**: 4 folders

## 🎯 Benefits

### ✅ Improved Organization
- Clear separation of concerns
- Easy to find relevant scripts
- Reduced cognitive load

### ✅ Reduced Duplication
- Eliminated 4 duplicate scripts
- Consolidated similar functionality
- Single source of truth

### ✅ Better Maintainability
- Core scripts easily identifiable
- Archive scripts preserved but out of the way
- Utility scripts grouped by function

### ✅ Documentation
- Clear structure documentation
- Script purposes documented
- Easy onboarding for new developers

## 🚀 Usage Guidelines

### Core Scripts
```powershell
# EntryPoint scripts (EP-01..EP-10)
py scripts/setup_db.py
py scripts/compute_signals.py
py scripts/backtest_runner.py
```

### Utility Scripts
```powershell
# Analysis and testing
py scripts/utility/analyze_warning.py
py scripts/utility/test_conformity.py
py scripts/utility/data_quality_audit.py
```

### Archive Scripts
```powershell
# Reference only - not for regular use
# Implementation phases and optimization scripts
```

## 🔄 Migration Notes

### Scripts Removed
- `create_portfolio_overview.py` (buggy version)
- `fix_data_integrity.py` (legacy)
- `fix_remaining_issues.py` (legacy)
- `compute_signals_fixed.py` (duplicate)

### Scripts Moved
- 10 scripts to `archive/` folder
- 14 scripts to `utility/` folder

### Scripts Updated
- README.md with new organization
- Script paths updated in documentation
- Utility script paths corrected
