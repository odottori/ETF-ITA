#!/usr/bin/env python3
"""
Report Session Manager - ETF Italia Project v10
Gestisce la serializzazione dei report con session ID univoco
"""

import sys
import os
import json
import uuid
from datetime import datetime
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ReportSessionManager:
    """Gestore sessioni report con ID univoco"""
    
    def __init__(self, base_reports_dir=None):
        if base_reports_dir is None:
            base_reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports')
        
        self.base_reports_dir = Path(base_reports_dir)
        self.analysis_dir = self.base_reports_dir / 'analysis'
        self.sessions_dir = self.base_reports_dir / 'sessions'
        
        # Crea directory se non esistono
        self.base_reports_dir.mkdir(exist_ok=True)
        self.analysis_dir.mkdir(exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)
    
    def create_session(self, session_type="full_analysis"):
        """Crea una nuova sessione di report"""
        
        # Genera session ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{session_type}_{timestamp}_{str(uuid.uuid4())[:8]}"
        
        # Crea directory sessione
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Salva session metadata
        session_metadata = {
            "session_id": session_id,
            "session_type": session_type,
            "created_at": datetime.now().isoformat(),
            "status": "created",
            "reports": []
        }
        
        metadata_file = session_dir / "session_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(session_metadata, f, indent=2)
        
        print(f" Session created: {session_id}")
        print(f"   Directory: {session_dir}")
        
        return session_id, session_dir
    
    def add_report_to_session(self, session_id, report_type, report_data, file_extension="json"):
        """Aggiunge un report alla sessione"""
        
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            raise FileNotFoundError(f"Session {session_id} not found")
        
        # Nome file report
        report_filename = f"{report_type}.{file_extension}"
        report_path = session_dir / report_filename
        
        # Salva report
        if file_extension == "json":
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
        elif file_extension == "md":
            with open(report_path, 'w') as f:
                f.write(report_data)
        else:
            with open(report_path, 'w') as f:
                f.write(str(report_data))
        
        # Aggiorna session metadata
        metadata_file = session_dir / "session_metadata.json"
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        metadata["reports"].append({
            "type": report_type,
            "filename": report_filename,
            "created_at": datetime.now().isoformat()
        })
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f" Report added: {report_filename}")
        return report_path
    
    def get_latest_session(self, session_type=None):
        """Ottiene la sessione più recente"""
        
        sessions = []
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                metadata_file = session_dir / "session_metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    if session_type is None or metadata.get("session_type") == session_type:
                        sessions.append((session_dir, metadata))
        
        if not sessions:
            return None, None
        
        # Ordina per created_at e prendi la più recente
        sessions.sort(key=lambda x: x[1]["created_at"], reverse=True)
        return sessions[0][0], sessions[0][1]
    
    def list_sessions(self):
        """Lista tutte le sessioni"""
        
        sessions = []
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                metadata_file = session_dir / "session_metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    sessions.append({
                        "session_id": metadata["session_id"],
                        "session_type": metadata["session_type"],
                        "created_at": metadata["created_at"],
                        "status": metadata["status"],
                        "reports_count": len(metadata["reports"])
                    })
        
        return sorted(sessions, key=lambda x: x["created_at"], reverse=True)

def demo_session_manager():
    """Demo del session manager"""
    
    print(" REPORT SESSION MANAGER - ETF Italia Project v10")
    print("=" * 60)
    
    manager = ReportSessionManager()
    
    # Crea nuova sessione
    session_id, session_dir = manager.create_session("full_analysis")
    
    # Aggiungi report fittizi
    health_data = {"status": "HEALTHY", "timestamp": datetime.now().isoformat()}
    stress_data = {"simulations": 1000, "risk_level": "HIGH"}
    performance_data = {"sharpe": 0.96, "cagr": 0.228}
    
    manager.add_report_to_session(session_id, "health_report", health_data)
    manager.add_report_to_session(session_id, "stress_test", stress_data)
    manager.add_report_to_session(session_id, "performance_summary", performance_data)
    
    # Lista sessioni
    print(f"\n Sessions disponibili:")
    for session in manager.list_sessions():
        print(f"    {session['session_id']}")
        print(f"      Type: {session['session_type']}")
        print(f"      Reports: {session['reports_count']}")
        print(f"      Created: {session['created_at']}")
    
    print(f"\n Session demo completed!")

if __name__ == "__main__":
    demo_session_manager()
