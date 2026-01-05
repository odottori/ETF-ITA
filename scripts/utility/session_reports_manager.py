#!/usr/bin/env python3
"""
Session Reports Manager - ETF Italia Project v10
Gestione centralizzata per report di sessione in docs/session_reports/
"""

import os
import json
from datetime import datetime
from pathlib import Path

def create_session_report(report_name, content, format_type='md'):
    """
    Crea un report di sessione in docs/session_reports/
    
    Args:
        report_name: Nome base del report (es. 'P2_Risk_Status')
        content: Contenuto del report (string per md, dict per json)
        format_type: 'md' o 'json'
    
    Returns:
        str: Path completo del file creato
    """
    # Get project root
    project_root = Path(__file__).parent.parent.parent
    session_reports_dir = project_root / 'docs' / 'session_reports'
    
    # Ensure directory exists
    session_reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create filename
    if format_type == 'md':
        filename = f"{report_name}_Report_{timestamp}.md"
        filepath = session_reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
    elif format_type == 'json':
        filename = f"{report_name}_Report_{timestamp}.json"
        filepath = session_reports_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(content, f, indent=2)
    else:
        raise ValueError(f"Format not supported: {format_type}")
    
    return str(filepath)

def get_latest_report(report_name, format_type='md'):
    """
    Recupera l'ultimo report per nome
    
    Args:
        report_name: Nome base del report
        format_type: 'md' o 'json'
    
    Returns:
        str: Path del report più recente o None
    """
    project_root = Path(__file__).parent.parent.parent
    session_reports_dir = project_root / 'docs' / 'session_reports'
    
    if not session_reports_dir.exists():
        return None
    
    # Find matching files
    pattern = f"{report_name}_Report_*.{format_type}"
    matching_files = list(session_reports_dir.glob(pattern))
    
    if not matching_files:
        return None
    
    # Return latest by modification time
    latest_file = max(matching_files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)

def list_session_reports():
    """
    Lista tutti i report di sessione
    
    Returns:
        list: Lista di tuple (filename, mtime, size)
    """
    project_root = Path(__file__).parent.parent.parent
    session_reports_dir = project_root / 'docs' / 'session_reports'
    
    if not session_reports_dir.exists():
        return []
    
    reports = []
    for file_path in session_reports_dir.glob('*'):
        if file_path.is_file():
            stat = file_path.stat()
            reports.append((
                file_path.name,
                datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                f"{stat.st_size} bytes"
            ))
    
    return sorted(reports, key=lambda x: x[1], reverse=True)
