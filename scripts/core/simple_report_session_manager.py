#!/usr/bin/env python3
"""
Simple Report Session Manager - ETF Italia Project v10
Gestisce la serializzazione dei report con timestamp univoco per gruppo
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SimpleReportSessionManager:
    """Gestore sessioni report con timestamp univoco per gruppo"""
    
    def __init__(self, base_reports_dir=None):
        if base_reports_dir is None:
            base_reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports')
        
        self.base_reports_dir = Path(base_reports_dir)
        self.sessions_dir = self.base_reports_dir / 'sessions'
        
        # Crea directory se non esistono
        self.base_reports_dir.mkdir(exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)
    
    def create_session(self):
        """Crea una nuova sessione con timestamp univoco"""
        
        # Genera timestamp univoco
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Crea directory sessione
        session_dir = self.sessions_dir / timestamp
        session_dir.mkdir(exist_ok=True)
        
        # Salva session info
        session_info = {
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "status": "created",
            "reports": []
        }
        
        info_file = session_dir / "session_info.json"
        with open(info_file, 'w') as f:
            json.dump(session_info, f, indent=2)
        
        print(f"📁 Session created: {timestamp}")
        print(f"   Directory: {session_dir}")
        
        return timestamp, session_dir
    
    def add_report_to_session(self, timestamp, report_type, report_data, file_extension="json"):
        """Aggiunge un report alla sessione"""
        
        session_dir = self.sessions_dir / timestamp
        if not session_dir.exists():
            raise FileNotFoundError(f"Session {timestamp} not found")
        
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
        
        # Aggiorna session info
        info_file = session_dir / "session_info.json"
        with open(info_file, 'r') as f:
            session_info = json.load(f)
        
        session_info["reports"].append({
            "type": report_type,
            "filename": report_filename,
            "created_at": datetime.now().isoformat()
        })
        
        with open(info_file, 'w') as f:
            json.dump(session_info, f, indent=2)
        
        print(f"📄 Report added: {report_filename}")
        return report_path
    
    def get_latest_session(self):
        """Ottiene la sessione più recente"""
        
        sessions = []
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                info_file = session_dir / "session_info.json"
                if info_file.exists():
                    sessions.append(session_dir)
        
        if not sessions:
            return None, None
        
        # Ordina per timestamp e prendi la più recente
        sessions.sort(reverse=True)
        latest_session = sessions[0]
        
        info_file = latest_session / "session_info.json"
        with open(info_file, 'r') as f:
            session_info = json.load(f)
        
        return latest_session.name, session_info
    
    def list_sessions(self):
        """Lista tutte le sessioni"""
        
        sessions = []
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                info_file = session_dir / "session_info.json"
                if info_file.exists():
                    with open(info_file, 'r') as f:
                        session_info = json.load(f)
                    
                    sessions.append({
                        "timestamp": session_info["timestamp"],
                        "created_at": session_info["created_at"],
                        "status": session_info["status"],
                        "reports_count": len(session_info["reports"])
                    })
        
        return sorted(sessions, key=lambda x: x["created_at"], reverse=True)

def demo_simple_session_manager():
    """Demo del simple session manager"""
    
    print("🔧 SIMPLE REPORT SESSION MANAGER - ETF Italia Project v10")
    print("=" * 60)
    
    manager = SimpleReportSessionManager()
    
    # Crea nuova sessione
    timestamp, session_dir = manager.create_session()
    
    # Aggiungi report fittizi
    health_data = {"status": "HEALTHY", "timestamp": datetime.now().isoformat()}
    stress_data = {"simulations": 1000, "risk_level": "HIGH"}
    performance_data = {"sharpe": 0.96, "cagr": 0.228}
    
    manager.add_report_to_session(timestamp, "health_report", health_data)
    manager.add_report_to_session(timestamp, "stress_test", stress_data)
    manager.add_report_to_session(timestamp, "performance_summary", performance_data)
    
    # Lista sessioni
    print(f"\n📋 Sessions disponibili:")
    for session in manager.list_sessions():
        print(f"   📁 {session['timestamp']}")
        print(f"      Reports: {session['reports_count']}")
        print(f"      Created: {session['created_at']}")
    
    print(f"\n✅ Simple session demo completed!")

if __name__ == "__main__":
    demo_simple_session_manager()
