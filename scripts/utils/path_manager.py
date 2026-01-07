"""
Path Manager - Centralizzazione path del progetto ETF_ITA v10.8

Gestisce tutti i path di data/, production/, backtests/, reports/, temp/
per garantire coerenza e facilità di manutenzione.
"""

import os
from datetime import datetime
from pathlib import Path

# Root del progetto
PROJECT_ROOT = Path(__file__).parent.parent.parent

class PathManager:
    """Gestisce tutti i path del progetto in modo centralizzato"""
    
    def __init__(self):
        self.root = PROJECT_ROOT
        
    # ==================== DATABASE ====================
    
    @property
    def db_path(self):
        """Path al database principale"""
        return self.root / 'data' / 'db' / 'etf_data.duckdb'
    
    def db_backup_path(self, timestamp=None):
        """Path per backup DB"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'db' / 'backups' / f'etf_data_backup_{timestamp}.duckdb'
    
    # ==================== PRODUCTION ====================
    
    def production_orders_path(self, timestamp=None):
        """Path per ordini PRODUCTION (strategy_engine)"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'production' / 'orders' / f'orders_{timestamp}.json'
    
    def production_forecast_path(self, timestamp=None):
        """Path per forecast (ordini proposti dry-run)"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'production' / 'forecasts' / f'forecast_{timestamp}.json'
    
    def production_postcast_path(self, timestamp=None):
        """Path per postcast (report post-esecuzione)"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'production' / 'postcasts' / f'postcast_{timestamp}.json'
    
    def production_kpi_path(self, timestamp=None):
        """Path per KPI production"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'production' / 'kpi' / f'kpi_{timestamp}.json'
    
    # ==================== BACKTEST ====================
    
    def backtest_run_dir(self, preset, timestamp=None):
        """Directory per singolo run backtest"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'backtests' / 'runs' / f'backtest_{preset}_{timestamp}'
    
    def backtest_orders_path(self, preset, timestamp=None):
        """Path per ordini backtest"""
        run_dir = self.backtest_run_dir(preset, timestamp)
        return run_dir / 'orders.json'
    
    def backtest_portfolio_path(self, preset, timestamp=None):
        """Path per evoluzione portfolio backtest"""
        run_dir = self.backtest_run_dir(preset, timestamp)
        return run_dir / 'portfolio.json'
    
    def backtest_kpi_path(self, preset, timestamp=None):
        """Path per KPI backtest"""
        run_dir = self.backtest_run_dir(preset, timestamp)
        return run_dir / 'kpi.json'
    
    def backtest_trades_path(self, preset, timestamp=None):
        """Path per dettaglio trade backtest"""
        run_dir = self.backtest_run_dir(preset, timestamp)
        return run_dir / 'trades.json'
    
    def backtest_summary_path(self, batch_timestamp=None):
        """Path per summary aggregato multi-preset"""
        if batch_timestamp is None:
            batch_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'backtests' / 'reports' / f'backtest_summary_{batch_timestamp}.json'
    
    # ==================== REPORTS ====================
    
    def session_dir(self, timestamp=None):
        """Directory per session reports"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.root / 'data' / 'reports' / 'sessions' / timestamp
    
    def health_check_dir(self, timestamp=None):
        """Directory per health check reports"""
        return self.session_dir(timestamp) / '01_health_checks'
    
    def data_quality_dir(self, timestamp=None):
        """Directory per data quality reports"""
        return self.session_dir(timestamp) / '02_data_quality'
    
    def guardrails_dir(self, timestamp=None):
        """Directory per guardrails reports"""
        return self.session_dir(timestamp) / '03_guardrails'
    
    def risk_management_dir(self, timestamp=None):
        """Directory per risk management reports"""
        return self.session_dir(timestamp) / '04_risk_management'
    
    def stress_tests_dir(self, timestamp=None):
        """Directory per stress tests"""
        return self.session_dir(timestamp) / '05_stress_tests'
    
    def strategy_analysis_dir(self, timestamp=None):
        """Directory per strategy analysis"""
        return self.session_dir(timestamp) / '06_strategy_analysis'
    
    def backtest_validation_dir(self, timestamp=None):
        """Directory per backtest validation"""
        return self.session_dir(timestamp) / '07_backtest_validation'
    
    def performance_summary_dir(self, timestamp=None):
        """Directory per performance summary"""
        return self.session_dir(timestamp) / '08_performance_summary'
    
    @property
    def current_session_path(self):
        """Path per current_session.json"""
        return self.root / 'data' / 'reports' / 'current_session.json'
    
    # ==================== TEMP ====================
    
    @property
    def temp_dir(self):
        """Directory per file temporanei"""
        return self.root / 'temp'
    
    def temp_file(self, filename):
        """Path per file temporaneo specifico"""
        return self.temp_dir / filename
    
    # ==================== CONFIG ====================
    
    @property
    def config_dir(self):
        """Directory config"""
        return self.root / 'config'
    
    @property
    def etf_universe_path(self):
        """Path per etf_universe.json"""
        return self.config_dir / 'etf_universe.json'
    
    @property
    def market_holidays_path(self):
        """Path per market_holidays.json"""
        return self.config_dir / 'market_holidays.json'
    
    # ==================== UTILITY ====================
    
    def ensure_dir(self, path):
        """Crea directory se non esiste"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return path
    
    def ensure_parent_dir(self, file_path):
        """Crea parent directory di un file se non esiste"""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        return file_path


# Singleton instance
_path_manager = None

def get_path_manager():
    """Ottieni istanza singleton PathManager"""
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


# Backward compatibility - funzioni legacy
def get_db_path():
    """Legacy: ottieni path DB"""
    return str(get_path_manager().db_path)


if __name__ == '__main__':
    # Test path manager
    pm = get_path_manager()
    
    print("📁 PATH MANAGER TEST")
    print("=" * 60)
    print(f"DB Path: {pm.db_path}")
    print(f"Production Orders: {pm.production_orders_path()}")
    print(f"Production Forecast: {pm.production_forecast_path()}")
    print(f"Production KPI: {pm.production_kpi_path()}")
    print(f"Backtest Run Dir: {pm.backtest_run_dir('full')}")
    print(f"Backtest KPI: {pm.backtest_kpi_path('full')}")
    print(f"Session Dir: {pm.session_dir()}")
    print(f"Health Check Dir: {pm.health_check_dir()}")
    print(f"Temp Dir: {pm.temp_dir}")
    print("✅ All paths OK")
