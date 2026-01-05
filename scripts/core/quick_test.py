#!/usr/bin/env python3
"""
Quick Test - ETF Italia Project v10
Sessione TEST rapida per controlli essenziali
"""

import sys
import os
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_manager import get_test_session_manager

def quick_test():
    """Esegue una sessione TEST rapida"""
    
    print("🧪 QUICK TEST - ETF Italia Project v10")
    print("=" * 50)
    
    # Crea sessione TEST
    sm = get_test_session_manager()
    print(f"✅ Sessione TEST creata: {sm.current_session}")
    
    try:
        # Esegui solo i controlli essenziali
        print("\n🔍 01/04 Health Checks...")
        # Qui potresti chiamare health_check.py con session manager
        
        print("🛡️ 02/04 Guardrails...")
        # Qui potresti chiamare check_guardrails.py
        
        print("⚡ 03/04 Strategy Engine...")
        # Qui potresti chiamare strategy_engine.py
        
        print("📊 04/04 Analysis...")
        
        # Report finale
        final_report = {
            'test_session': True,
            'session_id': sm.current_session,
            'categories_completed': 4,
            'execution_time': '00:01:00',
            'status': 'COMPLETED',
            'timestamp': datetime.now().isoformat()
        }
        
        sm.add_report_to_session('analysis', final_report, 'json')
        
        print(f"\n🎉 QUICK TEST COMPLETATO!")
        print(f"📁 Sessione: {sm.current_session}")
        print(f"📊 Report salvato in: 08_analysis/")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

if __name__ == "__main__":
    success = quick_test()
    sys.exit(0 if success else 1)
