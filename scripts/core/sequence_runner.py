#!/usr/bin/env python3
"""
Sequence Runner - ETF Italia Project v10
Gestisce l'esecuzione sequenziale degli script nella stessa sessione
"""

import sys
import os
import subprocess
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_manager import get_session_manager

# Mappatura degli script in sequenza ordinale
SCRIPT_SEQUENCE = {
    'health_check': ['health_check.py'],
    'automated_test_cycle': ['automated_test_cycle.py'],
    'check_guardrails': ['check_guardrails.py'],
    'risk_management': ['risk_management.py', 'enhanced_risk_management.py'],
    'stress_test': ['stress_test.py'],
    'strategy_engine': ['strategy_engine.py'],
    'backtest_runner': ['backtest_runner.py'],
    'performance_report_generator': ['performance_report_generator.py'],
    'analyze_schema_drift': ['analyze_schema_drift.py', 'detailed_schema_analysis.py']
}

# Ordine di esecuzione
EXECUTION_ORDER = [
    'health_check',
    'automated_test_cycle', 
    'check_guardrails',
    'risk_management',
    'stress_test',
    'strategy_engine',
    'backtest_runner',
    'performance_report_generator',
    'analyze_schema_drift'
]

def get_script_step(script_name):
    """Ritorna lo step numerico dello script nella sequenza"""
    for i, step in enumerate(EXECUTION_ORDER, 1):
        if script_name in step or any(script_name.endswith(s) for s in SCRIPT_SEQUENCE[step]):
            return i
    return None

def run_sequence_from(script_name):
    """Esegue la sequenza completa dallo script specificato in poi"""
    scripts_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(os.path.dirname(scripts_dir))
    
    # Trova lo step corrente
    current_step = get_script_step(script_name)
    if current_step is None:
        print(f"❌ Script '{script_name}' non trovato nella sequenza")
        return False
    
    print(f"\n🔄 SEQUENZA DA STEP {current_step}: {script_name}")
    print("=" * 60)
    
    # Esegui tutti gli script dallo step corrente in poi
    for step in EXECUTION_ORDER[current_step-1:]:
        print(f"\n📍 STEP {EXECUTION_ORDER.index(step) + 1}: {step.upper()}")
        print("-" * 40)
        
        # Trova lo script principale per questo step
        script_files = SCRIPT_SEQUENCE[step]
        main_script = None
        
        for script_file in script_files:
            script_path = os.path.join(scripts_dir, script_file)
            if os.path.exists(script_path):
                main_script = script_path
                break
        
        if not main_script:
            print(f"⚠️ Nessuno script trovato per {step}")
            continue
        
        # Esegui lo script
        try:
            result = subprocess.run([sys.executable, main_script], 
                                  capture_output=True, text=True, cwd=root_dir)
            
            if result.returncode != 0:
                print(f"❌ {step} fallito:")
                print(result.stderr)
                return False
            
            print(f"✅ {step} completato")
            
        except Exception as e:
            print(f"❌ Errore eseguendo {step}: {e}")
            return False
    
    print(f"\n🎉 SEQUENZA COMPLETATA (STEP {current_step}-{len(EXECUTION_ORDER)})")
    return True

def run_single_script(script_name):
    """Esegue solo lo script specificato usando la sessione esistente"""
    scripts_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(os.path.dirname(scripts_dir))
    
    # Trova il file dello script
    script_path = None
    for step, scripts in SCRIPT_SEQUENCE.items():
        for script_file in scripts:
            if script_name in script_file or script_name.endswith(script_file.replace('.py', '')):
                script_path = os.path.join(scripts_dir, script_file)
                break
        if script_path:
            break
    
    if not script_path or not os.path.exists(script_path):
        print(f"❌ Script '{script_name}' non trovato")
        return False
    
    print(f"\n🔍 ESECUZIONE SINGOLA: {script_name}")
    print("-" * 40)
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, cwd=root_dir)
        
        if result.returncode != 0:
            print(f"❌ {script_name} fallito:")
            print(result.stderr)
            return False
        
        print(f"✅ {script_name} completato")
        return True
        
    except Exception as e:
        print(f"❌ Errore eseguendo {script_name}: {e}")
        return False
