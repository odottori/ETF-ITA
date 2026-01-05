#!/usr/bin/env python3
"""
Session Reports Manager - ETF Italia Project v10
Gestione centralizzata per report di sessione in data/reports/sessions/
"""

import os
import json
from datetime import datetime
from pathlib import Path

def create_session_report(report_name, content, format_type='md'):
    """
    Crea un report di sessione in data/reports/sessions/<timestamp>/04_risk/
    
    Args:
        report_name: Nome base del report (es. 'P2_Risk_Status')
        content: Contenuto del report (string per md, dict per json)
        format_type: 'md' o 'json'
    
    Returns:
        str: Path completo del file creato
    """
    # Get project root
    project_root = Path(__file__).parent.parent.parent
    sessions_dir = project_root / 'data' / 'reports' / 'sessions'
    
    # Find current session
    current_session_file = sessions_dir.parent / 'current_session.json'
    if current_session_file.exists():
        with open(current_session_file, 'r') as f:
            session_data = json.load(f)
            current_session = session_data['current_session']
    else:
        # Fallback to latest session
        session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
        if not session_dirs:
            raise FileNotFoundError("No session found")
        current_session = max(session_dirs, key=lambda d: d.stat().st_mtime).name
    
    # Use risk subdirectory for risk reports
    risk_dir = sessions_dir / current_session / '04_risk'
    risk_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename
    if format_type == 'md':
        filename = f"{report_name}.md"
        filepath = risk_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
    elif format_type == 'json':
        filename = f"{report_name}.json"
        filepath = risk_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(content, f, indent=2)
    else:
        raise ValueError(f"Format not supported: {format_type}")
    
    return str(filepath)

def get_latest_report(report_name, format_type='md'):
    """
    Recupera l'ultimo report per nome dalla cartella risk
    
    Args:
        report_name: Nome base del report
        format_type: 'md' o 'json'
    
    Returns:
        str: Path del report più recente o None
    """
    project_root = Path(__file__).parent.parent.parent
    sessions_dir = project_root / 'data' / 'reports' / 'sessions'
    
    # Find current session
    current_session_file = sessions_dir.parent / 'current_session.json'
    if current_session_file.exists():
        with open(current_session_file, 'r') as f:
            session_data = json.load(f)
            current_session = session_data['current_session']
    else:
        # Fallback to latest session
        session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
        if not session_dirs:
            return None
        current_session = max(session_dirs, key=lambda d: d.stat().st_mtime).name
    
    risk_dir = sessions_dir / current_session / '04_risk'
    
    if not risk_dir.exists():
        return None
    
    # Find matching files
    pattern = f"{report_name}.{format_type}"
    matching_files = list(risk_dir.glob(pattern))
    
    if not matching_files:
        return None
    
    # Return latest by modification time
    latest_file = max(matching_files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)

def list_session_reports():
    """
    Lista tutti i report di sessione dalla cartella risk
    
    Returns:
        list: Lista di tuple (filename, mtime, size)
    """
    project_root = Path(__file__).parent.parent.parent
    sessions_dir = project_root / 'data' / 'reports' / 'sessions'
    
    # Find current session
    current_session_file = sessions_dir.parent / 'current_session.json'
    if current_session_file.exists():
        with open(current_session_file, 'r') as f:
            session_data = json.load(f)
            current_session = session_data['current_session']
    else:
        # Fallback to latest session
        session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
        if not session_dirs:
            return []
        current_session = max(session_dirs, key=lambda d: d.stat().st_mtime).name
    
    risk_dir = sessions_dir / current_session / '04_risk'
    
    if not risk_dir.exists():
        return []
    
    reports = []
    for file_path in risk_dir.glob('*'):
        if file_path.is_file():
            stat = file_path.stat()
            reports.append((
                file_path.name,
                datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                f"{stat.st_size} bytes"
            ))
    
    return sorted(reports, key=lambda x: x[1], reverse=True)
