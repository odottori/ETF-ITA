#!/usr/bin/env python3
"""
Complete System Validation - ETF Italia Project v10
Sessione completa di test e certificazioni per verificare ogni componente
"""

import sys
import os
import duckdb
import json
import subprocess
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_script(script_path, description, session_dir):
    """Esegue uno script e cattura l'output"""
    print(f"\n {description}")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ['py', script_path], 
            capture_output=True, 
            text=True, 
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        
        print(f" Exit Code: {result.returncode}")
        
        if result.stdout:
            print(f" Output:\n{result.stdout}")
        
        if result.stderr:
            print(f"️  Errors:\n{result.stderr}")
        
        # Salva output in session report
        script_name = os.path.basename(script_path).replace('.py', '')
        output_file = os.path.join(session_dir, 'automated', f"{script_name}_output.txt")
        
        with open(output_file, 'w') as f:
            f.write(f"=== {description} ===\n")
            f.write(f"Exit Code: {result.returncode}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"\n=== STDOUT ===\n{result.stdout}\n")
            if result.stderr:
                f.write(f"\n=== STDERR ===\n{result.stderr}\n")
        
        return result.returncode == 0, result.returncode
        
    except Exception as e:
        print(f" Errore esecuzione {script_path}: {e}")
        return False, -1

def complete_system_validation():
    """Sessione completa di validazione sistema"""
    
    print("COMPLETE SYSTEM VALIDATION - ETF Italia Project v10")
    print("=" * 80)
    
    # Crea session directory
    session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports', 'sessions', session_timestamp)
    automated_dir = os.path.join(session_dir, 'automated')
    analysis_dir = os.path.join(session_dir, 'analysis')
    
    os.makedirs(automated_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    
    print(f"Session Directory: {session_dir}")
    
    # Session info
    session_info = {
        "session_id": session_timestamp,
        "timestamp": datetime.now().isoformat(),
        "session_type": "complete_system_validation",
        "description": "Full system validation with all available tests",
        "status": "running"
    }
    
    session_info_file = os.path.join(session_dir, 'session_info.json')
    with open(session_info_file, 'w') as f:
        json.dump(session_info, f, indent=2)
    
    # Scripts da eseguire in ordine logico
    validation_scripts = [
        {
            "path": "scripts/core/setup_db.py",
            "description": "EP-01: Database Setup",
            "critical": True
        },
        {
            "path": "scripts/core/load_trading_calendar.py", 
            "description": "EP-02: Trading Calendar Load",
            "critical": True
        },
        {
            "path": "scripts/core/ingest_data.py",
            "description": "EP-03: Data Ingestion with Quality Gates",
            "critical": True
        },
        {
            "path": "scripts/core/health_check.py",
            "description": "EP-04: System Health Check",
            "critical": True
        },
        {
            "path": "scripts/core/compute_signals.py",
            "description": "EP-05: Signal Engine Computation",
            "critical": True
        },
        {
            "path": "scripts/core/check_guardrails.py",
            "description": "EP-06: Risk Guardrails Check",
            "critical": True
        },
        {
            "path": "scripts/core/strategy_engine.py",
            "description": "EP-07: Strategy Engine (dry-run)",
            "args": ["--dry-run"],
            "critical": True
        },
        {
            "path": "scripts/core/update_ledger.py",
            "description": "EP-08: Ledger Update (NO COMMIT)",
            "args": ["--dry-run"],
            "critical": False  # Non facciamo commit in validation
        },
        {
            "path": "scripts/core/backtest_runner.py",
            "description": "EP-09: Backtest Runner",
            "critical": True
        },
        {
            "path": "scripts/core/stress_test.py",
            "description": "EP-10: Monte Carlo Stress Test",
            "critical": True
        },
        {
            "path": "scripts/core/sanity_check.py",
            "description": "EP-11: Sanity Check (bloccante)",
            "critical": True
        },
        {
            "path": "analysis/scripts/comprehensive_risk_analysis.py",
            "description": "Risk Analysis Complete",
            "critical": False
        },
        {
            "path": "scripts/core/automated_test_cycle.py",
            "description": "Automated Test Cycle",
            "critical": False
        }
    ]
    
    # Esegui tutti gli script
    results = []
    critical_failures = []
    
    for script in validation_scripts:
        script_path = script["path"]
        description = script["description"]
        critical = script["critical"]
        
        success, exit_code = run_script(script_path, description, session_dir)
        
        results.append({
            "script": script_path,
            "description": description,
            "success": success,
            "exit_code": exit_code,
            "critical": critical
        })
        
        if critical and not success:
            critical_failures.append(script_path)
            print(f" CRITICAL FAILURE: {script_path}")
    
    # Database integrity check
    print(f"\n DATABASE INTEGRITY CHECK")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    try:
        conn = duckdb.connect(db_path)
        
        # Check tables
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        tables = conn.execute(tables_query).fetchall()
        
        print(f" Database Tables: {len(tables)}")
        for table in tables:
            table_name = table[0]
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            count = conn.execute(count_query).fetchone()[0]
            print(f"   {table_name}: {count:,} records")
        
        # Check data quality
        data_quality_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN adj_close IS NULL THEN 1 END) as null_adj_close,
            COUNT(CASE WHEN volume < 0 THEN 1 END) as negative_volume,
            COUNT(CASE WHEN high < low THEN 1 END) as invalid_ohlc
        FROM market_data
        """
        
        quality = conn.execute(data_quality_query).fetchone()
        print(f"\n Data Quality:")
        print(f"   Total Records: {quality[0]:,}")
        print(f"   NULL Adj Close: {quality[1]}")
        print(f"   Negative Volume: {quality[2]}")
        print(f"   Invalid OHLC: {quality[3]}")
        
        conn.close()
        
        db_integrity = True
        
    except Exception as e:
        print(f" Database integrity check failed: {e}")
        db_integrity = False
    
    # Report finale
    print(f"\n VALIDATION SUMMARY")
    print("=" * 60)
    
    total_scripts = len(results)
    successful_scripts = sum(1 for r in results if r["success"])
    failed_scripts = total_scripts - successful_scripts
    critical_failed = len(critical_failures)
    
    print(f" Total Scripts: {total_scripts}")
    print(f" Successful: {successful_scripts}")
    print(f" Failed: {failed_scripts}")
    print(f" Critical Failures: {critical_failed}")
    print(f"️  Database Integrity: {' OK' if db_integrity else ' FAILED'}")
    
    # Overall status
    if critical_failed > 0 or not db_integrity:
        overall_status = "CRITICAL_FAILURE"
        status_color = ""
    elif failed_scripts > 0:
        overall_status = "PARTIAL_SUCCESS"
        status_color = ""
    else:
        overall_status = "FULL_SUCCESS"
        status_color = ""
    
    print(f"\n{status_color} OVERALL STATUS: {overall_status}")
    
    # Update session info
    session_info.update({
        "status": overall_status,
        "results": {
            "total_scripts": total_scripts,
            "successful": successful_scripts,
            "failed": failed_scripts,
            "critical_failures": critical_failed,
            "database_integrity": db_integrity
        },
        "script_results": results
    })
    
    with open(session_info_file, 'w') as f:
        json.dump(session_info, f, indent=2)
    
    # Salva report dettagliato
    validation_report = {
        "session_id": session_timestamp,
        "timestamp": datetime.now().isoformat(),
        "validation_type": "complete_system_validation",
        "overall_status": overall_status,
        "summary": {
            "total_scripts": total_scripts,
            "successful": successful_scripts,
            "failed": failed_scripts,
            "critical_failures": critical_failed,
            "database_integrity": db_integrity
        },
        "script_results": results,
        "database_stats": {
            "tables": len(tables) if 'tables' in locals() else 0,
            "total_records": quality[0] if 'quality' in locals() else 0,
            "data_quality_issues": {
                "null_adj_close": quality[1] if 'quality' in locals() else 0,
                "negative_volume": quality[2] if 'quality' in locals() else 0,
                "invalid_ohlc": quality[3] if 'quality' in locals() else 0
            }
        }
    }
    
    report_file = os.path.join(analysis_dir, 'complete_validation_report.json')
    with open(report_file, 'w') as f:
        json.dump(validation_report, f, indent=2)
    
    print(f"\n Validation Report: {report_file}")
    print(f"Session Directory: {session_dir}")
    
    return overall_status == "FULL_SUCCESS"

if __name__ == "__main__":
    success = complete_system_validation()
    sys.exit(0 if success else 1)
