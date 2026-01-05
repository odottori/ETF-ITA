#!/usr/bin/env python3
"""
Session Manager - ETF Italia Project v10
Gestione centralizzata delle sessioni con singola session per run
"""

import os
import json
from datetime import datetime
from pathlib import Path

class SessionManager:
    def __init__(self, base_reports_dir=None):
        if base_reports_dir is None:
            base_reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports', 'sessions')
        
        self.base_reports_dir = Path(base_reports_dir)
        self.current_session = None
        
        # Carica sessione esistente o creane una nuova
        self._load_or_create_session()
        
    def _load_or_create_session(self):
        """Carica sessione esistente da file o creane una nuova"""
        session_file = self.base_reports_dir.parent / 'current_session.json'
        
        if session_file.exists():
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    self.current_session = session_data['current_session']
                    return
            except:
                pass
        
        # Se non esiste o c'è errore, creane una nuova
        self.create_session()
        
        # Salva la sessione corrente
        with open(session_file, 'w') as f:
            json.dump({
                'current_session': self.current_session,
                'created_at': datetime.now().isoformat()
            }, f, indent=2)
        
    def create_session(self, test_mode=False):
        """Crea una nuova sessione con timestamp"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if test_mode:
            timestamp += "_TEST"
        
        session_dir = self.base_reports_dir / timestamp
        
        # Crea tutte le sottocartelle della sessione con prefissi ordinali
        subdirs = {
            '01_health_checks': 'health_checks',
            '02_automated': 'automated', 
            '03_guardrails': 'guardrails',
            '04_stress_tests': 'stress_tests',
            '05_strategy': 'strategy',
            '06_backtests': 'backtests',
            '07_performance': 'performance',
            '08_analysis': 'analysis'
        }
        
        # In test mode, crea solo le cartelle essenziali
        if test_mode:
            essential_subdirs = {
                '01_health_checks': 'health_checks',
                '03_guardrails': 'guardrails', 
                '05_strategy': 'strategy',
                '08_analysis': 'analysis'
            }
            subdirs = essential_subdirs
        
        for subdir_name in subdirs.keys():
            (session_dir / subdir_name).mkdir(parents=True, exist_ok=True)
        
        self.current_session = timestamp
        self.subdir_mapping = subdirs  # Salva mapping per uso futuro
        self.test_mode = test_mode
        return timestamp, session_dir
    
    def get_current_session_dir(self):
        """Restituisce la directory della sessione corrente"""
        if not self.current_session:
            timestamp, _ = self.create_session()
        
        return self.base_reports_dir / self.current_session
    
    def get_subdir_path(self, subdir_name):
        """Restituisce il path per una sottocartella specifica"""
        session_dir = self.get_current_session_dir()
        
        # Se abbiamo il mapping, usalo per trovare il nome con prefisso
        if hasattr(self, 'subdir_mapping'):
            for prefixed_name, logical_name in self.subdir_mapping.items():
                if logical_name == subdir_name:
                    return session_dir / prefixed_name
        
        # Fallback: cerca direttamente la sottocartella
        for item in session_dir.iterdir():
            if item.is_dir() and subdir_name in item.name:
                return item
        
        # Ultimate fallback: usa nome originale
        return session_dir / subdir_name
    
    def add_report_to_session(self, report_type, report_data, format_type='json'):
        """Aggiunge un report alla sessione corrente"""
        if not self.current_session:
            self.create_session()
        
        # Mappa report type → sottocartella corretta
        subdir_mapping = {
            'health_checks': 'health_checks',
            'strategy': 'strategy',
            'automated_test_cycle': 'automated',
            'stress_test': 'stress_tests',
            'guardrails': 'guardrails',
            'backtest': 'backtests',
            'performance': 'performance'
        }
        
        subdir_name = subdir_mapping.get(report_type, 'analysis')
        subdir = self.get_subdir_path(subdir_name)
        
        if format_type == 'json':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{report_type}_{timestamp}.json"
            filepath = subdir / filename
            
            with open(filepath, 'w') as f:
                json.dump(report_data, f, indent=2)
        
        elif format_type == 'md':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{report_type}_{timestamp}.md"
            filepath = subdir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_data)
        
        return filepath
    
    def create_backtest_dir(self, run_id):
        """Crea i file del backtest direttamente nella cartella backtests"""
        backtest_dir = self.get_subdir_path('backtests')
        return backtest_dir
    
    def create_test_session(self):
        """Crea una sessione di test con solo le cartelle essenziali"""
        return self.create_session(test_mode=True)
    
    def get_session_summary(self):
        """Restituisce un riepilogo della sessione corrente"""
        if not self.current_session:
            return None
        
        session_dir = self.get_current_session_dir()
        summary = {
            'session_id': self.current_session,
            'created_at': datetime.now().isoformat(),
            'reports': {}
        }
        
        for subdir in session_dir.iterdir():
            if subdir.is_dir():
                files = list(subdir.iterdir())
                summary['reports'][subdir.name] = {
                    'count': len(files),
                    'files': [f.name for f in files]
                }
        
        return summary

# Singleton globale
_session_manager = None

def get_session_manager():
    """Restituisce l'istanza singleton del session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

def get_test_session_manager():
    """Crea e restituisce un session manager per test"""
    sm = SessionManager()
    sm.create_test_session()
    return sm
