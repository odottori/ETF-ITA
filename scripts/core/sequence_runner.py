#!/usr/bin/env python3
"""
Sequence Runner - ETF Italia Project v10
Gestisce l'esecuzione sequenziale degli script nella stessa sessione
"""

import sys
import os
import subprocess
from datetime import datetime
import time
import threading
import queue

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


def _run_script_with_progress(script_path, root_dir):
    q = queue.Queue()

    def _reader(pipe, stream_name):
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                q.put((stream_name, line))
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    proc = subprocess.Popen(
        [sys.executable, script_path],
        cwd=root_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    t_out = threading.Thread(target=_reader, args=(proc.stdout, 'stdout'), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, 'stderr'), daemon=True)
    t_out.start()
    t_err.start()

    last_output_ts = time.time()
    last_dot_ts = time.time()
    dots_printed = False

    while True:
        try:
            stream_name, line = q.get(timeout=0.2)
            if dots_printed:
                print("")
                dots_printed = False
            if stream_name == 'stderr':
                print(line.rstrip("\n"))
            else:
                print(line.rstrip("\n"))
            last_output_ts = time.time()
            continue
        except queue.Empty:
            pass

        if proc.poll() is not None:
            break

        now = time.time()
        if now - last_output_ts >= 1.0 and now - last_dot_ts >= 1.0:
            print(".", end="", flush=True)
            dots_printed = True
            last_dot_ts = now

    while True:
        try:
            stream_name, line = q.get_nowait()
            if dots_printed:
                print("")
                dots_printed = False
            if stream_name == 'stderr':
                print(line.rstrip("\n"))
            else:
                print(line.rstrip("\n"))
        except queue.Empty:
            break

    if dots_printed:
        print("")

    return proc.returncode

def run_sequence_from(script_name):
    """Esegue la sequenza completa dallo script specificato in poi"""
    scripts_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(os.path.dirname(scripts_dir))
    
    # Trova lo step corrente
    current_step = get_script_step(script_name)
    if current_step is None:
        print(f"ERROR: Script '{script_name}' non trovato nella sequenza")
        return False
    
    print(f"\nSEQUENZA DA STEP {current_step}: {script_name}")
    print("=" * 60)
    
    # Esegui tutti gli script dallo step corrente in poi
    for step in EXECUTION_ORDER[current_step-1:]:
        print(f"\nSTEP {EXECUTION_ORDER.index(step) + 1}: {step.upper()}")
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
            print(f"WARN: Nessuno script trovato per {step}")
            continue
        
        # Esegui lo script
        try:
            return_code = _run_script_with_progress(main_script, root_dir)
            
            if return_code != 0:
                print(f"ERROR: {step} fallito:")
                return False
            
            print(f"OK: {step} completato")
            
        except Exception as e:
            print(f"ERROR: Errore eseguendo {step}: {e}")
            return False
    
    print(f"\nSEQUENZA COMPLETATA (STEP {current_step}-{len(EXECUTION_ORDER)})")
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
        print(f"ERROR: Script '{script_name}' non trovato")
        return False
    
    print(f"\nESECUZIONE SINGOLA: {script_name}")
    print("-" * 40)
    
    try:
        return_code = _run_script_with_progress(script_path, root_dir)
        
        if return_code != 0:
            print(f"ERROR: {script_name} fallito:")
            return False
        
        print(f"OK: {script_name} completato")
        return True
        
    except Exception as e:
        print(f"ERROR: Errore eseguendo {script_name}: {e}")
        return False
