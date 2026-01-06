# Scripts Organization - ETF-ITA v10.7.8

## Production Scripts (core/) - 17 files

### Data Pipeline
- `ingest_data.py` - Data ingestion from Yahoo Finance
- `load_trading_calendar.py` - Trading calendar management
- `setup_db.py` - Database setup and views

### Signal Generation
- `compute_signals.py` - Calculate momentum scores and signals
- `spike_detector.py` - Detect price spikes
- `zombie_exclusion_enforcer.py` - Filter illiquid ETFs

### Strategy Engine
- `strategy_engine.py` - Core strategy logic
- `execute_orders.py` - Order execution with tax logic
- `update_ledger.py` - Portfolio ledger updates
- `update_tax_loss_carryforward.py` - Tax loss carryforward

### Risk Management
- `enhanced_risk_management.py` - Advanced risk controls
- `diversification_guardrails.py` - Diversification limits
- `vol_targeting.py` - Volatility targeting

### Backtesting
- `backtest_engine.py` - Realistic backtesting simulation
- `backtest_runner.py` - Backtest execution

### System Management
- `health_check.py` - System health monitoring
- `session_manager.py` - Session management

## Utility Scripts (utility/) - 2 files
- `data_quality_audit.py` - Data quality validation
- `extend_historical_data.py` - Historical data extension

## Archive (archive/) - 0 files
- Completely cleaned of obsolete files

## Total: 19 production-ready scripts
Down from 120+ files to 19 essential scripts.
