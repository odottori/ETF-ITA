#!/usr/bin/env python3
"""
Complete System Test - ETF Italia Project v10
Test completo di tutti gli EntryPoint con ottimizzazione automatica
"""

import sys
import os
import json
import duckdb
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def complete_system_test():
    """Test completo del sistema con ottimizzazione automatica"""
    
    print("COMPLETE SYSTEM TEST - ETF Italia Project v10")
    print("=" * 70)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'overall_status': 'PENDING'
        }
        
        print("🔍 Inizio test completo sistema...")
        
        # 1. EP-01: Setup Database Test
        print("\nEP-01: Setup Database Test...")
        
        try:
            # Verifica tabelle principali
            tables = conn.execute("SHOW TABLES").fetchall()
            required_tables = [
                'market_data', 'trading_calendar', 'symbol_registry',
                'fiscal_ledger', 'signals', 'risk_metrics',
                'ingestion_audit', 'staging_data'
            ]
            
            missing_tables = [t for t in required_tables if t not in [table[0] for table in tables]]
            
            if missing_tables:
                print(f"FAIL: Tabelle mancanti: {missing_tables}")
                test_results['tests']['ep01'] = {'status': 'FAILED', 'missing_tables': missing_tables}
            else:
                print("PASS: Tutte le tabelle presenti")
                test_results['tests']['ep01'] = {'status': 'PASSED', 'tables_count': len(tables)}
        
        except Exception as e:
            print(f"ERROR: EP-01 Error: {e}")
            test_results['tests']['ep01'] = {'status': 'ERROR', 'error': str(e)}
        
        # 2. EP-02: Trading Calendar Test
        print("\nEP-02: Trading Calendar Test...")
        
        try:
            calendar_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_days,
                COUNT(CASE WHEN is_open = TRUE THEN 1 END) as trading_days,
                COUNT(CASE WHEN is_open = FALSE THEN 1 END) as holidays,
                MIN(date) as start_date,
                MAX(date) as end_date
            FROM trading_calendar
            WHERE venue = 'BIT'
            """).fetchone()
            
            if calendar_stats[0] > 0:
                print(f"PASS: Calendar BIT: {calendar_stats[0]} giorni totali")
                print(f"   Trading days: {calendar_stats[1]} | Holidays: {calendar_stats[2]}")
                print(f"   Periodo: {calendar_stats[3]} → {calendar_stats[4]}")
                test_results['tests']['ep02'] = {'status': 'PASSED', 'stats': dict(zip(['total', 'trading', 'holidays', 'start', 'end'], calendar_stats))}
            else:
                print("FAIL: Nessun dato calendar")
                test_results['tests']['ep02'] = {'status': 'FAILED', 'error': 'No calendar data'}
        
        except Exception as e:
            print(f"ERROR: EP-02 Error: {e}")
            test_results['tests']['ep02'] = {'status': 'ERROR', 'error': str(e)}
        
        # 3. EP-03: Data Ingestion Test
        print("\nEP-03: Data Ingestion Test...")
        
        try:
            data_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT symbol) as symbols,
                MIN(date) as start_date,
                MAX(date) as end_date,
                COUNT(DISTINCT date) as unique_dates
            FROM market_data
            """).fetchone()
            
            if data_stats[0] > 0:
                print(f"PASS: Market data: {data_stats[0]} records totali")
                print(f"   Simboli: {data_stats[1]} | Date: {data_stats[4]} uniche")
                print(f"   Periodo: {data_stats[2]} → {data_stats[3]}")
                
                # Quality check
                quality_issues = conn.execute("""
                SELECT COUNT(*) FROM market_data 
                WHERE close <= 0 OR adj_close <= 0 OR volume < 0
                """).fetchone()[0]
                
                if quality_issues == 0:
                    print("PASS: Quality check passed")
                    test_results['tests']['ep03'] = {'status': 'PASSED', 'stats': dict(zip(['total', 'symbols', 'start', 'end', 'dates'], data_stats))}
                else:
                    print(f"WARN: Quality issues: {quality_issues}")
                    test_results['tests']['ep03'] = {'status': 'WARNING', 'quality_issues': quality_issues}
            else:
                print("FAIL: Nessun dato market")
                test_results['tests']['ep03'] = {'status': 'FAILED', 'error': 'No market data'}
        
        except Exception as e:
            print(f"ERROR: EP-03 Error: {e}")
            test_results['tests']['ep03'] = {'status': 'ERROR', 'error': str(e)}
        
        # 4. EP-04: Health Check Test
        print("\nEP-04: Health Check Test...")
        
        try:
            # Verifica integrità dati
            integrity_issues = 0
            
            # Check for gaps
            gaps = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT date FROM trading_calendar 
                WHERE venue = 'BIT' AND is_open = TRUE
                EXCEPT
                SELECT DISTINCT date FROM market_data
                WHERE date >= '2020-01-01'
            )
            """).fetchone()[0]
            
            integrity_issues += gaps
            
            # Check zombie prices
            zombies = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT symbol, md.date, close, volume
                FROM market_data md
                JOIN trading_calendar tc ON md.date = tc.date
                WHERE tc.venue = 'BIT' AND tc.is_open = TRUE
                AND md.volume = 0
                GROUP BY symbol, md.date, close, volume
                HAVING COUNT(*) > 1
            )
            """).fetchone()[0]
            
            integrity_issues += zombies
            
            if integrity_issues == 0:
                print("PASS: Health check passed")
                test_results['tests']['ep04'] = {'status': 'PASSED', 'integrity_issues': 0}
            else:
                print(f"WARN: Integrity issues: {integrity_issues}")
                test_results['tests']['ep04'] = {'status': 'WARNING', 'integrity_issues': integrity_issues}
        
        except Exception as e:
            print(f"ERROR: EP-04 Error: {e}")
            test_results['tests']['ep04'] = {'status': 'ERROR', 'error': str(e)}
        
        # 5. EP-05: Signals Test
        print("\nEP-05: Signals Test...")
        
        try:
            signal_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_signals,
                COUNT(DISTINCT symbol) as symbols,
                COUNT(DISTINCT date) as dates,
                COUNT(CASE WHEN signal_state = 'RISK_ON' THEN 1 END) as risk_on,
                COUNT(CASE WHEN signal_state = 'RISK_OFF' THEN 1 END) as risk_off,
                COUNT(CASE WHEN signal_state = 'HOLD' THEN 1 END) as hold,
                AVG(risk_scalar) as avg_risk_scalar
            FROM signals
            """).fetchone()
            
            if signal_stats[0] > 0:
                print(f"PASS: Signals: {signal_stats[0]} totali")
                print(f"   Simboli: {signal_stats[1]} | Date: {signal_stats[2]}")
                print(f"   RISK_ON: {signal_stats[3]} | RISK_OFF: {signal_stats[4]} | HOLD: {signal_stats[5]}")
                print(f"   Avg risk scalar: {signal_stats[6]:.3f}")
                test_results['tests']['ep05'] = {'status': 'PASSED', 'stats': dict(zip(['total', 'symbols', 'dates', 'risk_on', 'risk_off', 'hold', 'avg_scalar'], signal_stats))}
            else:
                print("FAIL: Nessun segnale")
                test_results['tests']['ep05'] = {'status': 'FAILED', 'error': 'No signals'}
        
        except Exception as e:
            print(f"ERROR: EP-05 Error: {e}")
            test_results['tests']['ep05'] = {'status': 'ERROR', 'error': str(e)}
        
        # 6. EP-06: Guardrails Test
        print("\nEP-06: Guardrails Test...")
        
        try:
            # Simula check guardrails
            high_vol_check = conn.execute("""
            SELECT COUNT(*) FROM risk_metrics 
            WHERE volatility_20d > 0.25
            AND date >= CURRENT_DATE - INTERVAL '7 days'
            """).fetchone()[0]
            
            spy_guard_check = conn.execute("""
            SELECT COUNT(*) FROM risk_metrics 
            WHERE symbol = '^GSPC' 
            AND adj_close < sma_200
            AND date >= CURRENT_DATE - INTERVAL '7 days'
            """).fetchone()[0]
            
            guardrail_issues = high_vol_check + spy_guard_check
            
            if guardrail_issues == 0:
                print("PASS: Guardrails check passed")
                test_results['tests']['ep06'] = {'status': 'PASSED', 'issues': 0}
            else:
                print(f"WARN: Guardrail issues: {guardrail_issues}")
                test_results['tests']['ep06'] = {'status': 'WARNING', 'issues': guardrail_issues}
        
        except Exception as e:
            print(f"ERROR: EP-06 Error: {e}")
            test_results['tests']['ep06'] = {'status': 'ERROR', 'error': str(e)}
        
        # 7. EP-07: Strategy Engine Test
        print("\nEP-07: Strategy Engine Test...")
        
        try:
            # Verifica che strategy engine possa generare ordini
            # Simulazione semplice
            orders_count = conn.execute("""
            SELECT COUNT(*) FROM signals 
            WHERE signal_state != 'HOLD'
            AND date >= CURRENT_DATE - INTERVAL '7 days'
            """).fetchone()[0]
            
            if orders_count > 0:
                print(f"PASS: Strategy engine ready: {orders_count} ordini potenziali")
                test_results['tests']['ep07'] = {'status': 'PASSED', 'potential_orders': orders_count}
            else:
                print("WARN: No active signals")
                test_results['tests']['ep07'] = {'status': 'WARNING', 'no_active_signals': True}
        
        except Exception as e:
            print(f"ERROR: EP-07 Error: {e}")
            test_results['tests']['ep07'] = {'status': 'ERROR', 'error': str(e)}
        
        # 8. EP-08: Ledger Test
        print("\nEP-08: Ledger Test...")
        
        try:
            ledger_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                COUNT(DISTINCT date) as active_days,
                COUNT(CASE WHEN type = 'DEPOSIT' THEN 1 END) as deposits,
                COUNT(CASE WHEN type = 'BUY' THEN 1 END) as buys,
                COUNT(CASE WHEN type = 'SELL' THEN 1 END) as sells,
                COUNT(CASE WHEN type = 'INTEREST' THEN 1 END) as interests
            FROM fiscal_ledger
            """).fetchone()
            
            if ledger_stats[0] > 0:
                print(f"PASS: Ledger: {ledger_stats[0]} transazioni")
                print(f"   Depositi: {ledger_stats[2]} | Buy: {ledger_stats[3]} | Sell: {ledger_stats[4]}")
                print(f"   Interessi: {ledger_stats[5]} | Giorni attivi: {ledger_stats[1]}")
                test_results['tests']['ep08'] = {'status': 'PASSED', 'stats': dict(zip(['total', 'days', 'deposits', 'buys', 'sells', 'interests'], ledger_stats))}
            else:
                print("WARN: Ledger vuoto")
                test_results['tests']['ep08'] = {'status': 'WARNING', 'empty': True}
        
        except Exception as e:
            print(f"ERROR: EP-08 Error: {e}")
            test_results['tests']['ep08'] = {'status': 'ERROR', 'error': str(e)}
        
        # 9. EP-09: Backtest Runner Test
        print("\nEP-09: Backtest Runner Test...")
        
        try:
            # Verifica dati per backtest
            backtest_data = conn.execute("""
            SELECT COUNT(*) as data_points
            FROM portfolio_summary
            """).fetchone()[0]
            
            if backtest_data > 0:  # Almeno qualche dato
                print(f"PASS: Backtest ready: {backtest_data} data points")
                test_results['tests']['ep09'] = {'status': 'PASSED', 'data_points': backtest_data}
            else:
                print(f"WARN: Insufficient data: {backtest_data} points")
                test_results['tests']['ep09'] = {'status': 'WARNING', 'insufficient_data': backtest_data}
        
        except Exception as e:
            print(f"ERROR: EP-09 Error: {e}")
            test_results['tests']['ep09'] = {'status': 'ERROR', 'error': str(e)}
        
        # 10. EP-10: Stress Test Test
        print("\nEP-10: Stress Test Test...")
        
        try:
            # Verifica dati per stress test
            stress_data = conn.execute("""
            SELECT COUNT(*) as returns_count
            FROM portfolio_summary
            """).fetchone()[0]
            
            if stress_data > 0:  # Almeno qualche dato
                print(f"PASS: Stress test ready: {stress_data} returns")
                test_results['tests']['ep10'] = {'status': 'PASSED', 'returns_count': stress_data}
            else:
                print(f"WARN: Insufficient data: {stress_data} returns")
                test_results['tests']['ep10'] = {'status': 'WARNING', 'insufficient_data': stress_data}
        
        except Exception as e:
            print(f"ERROR: EP-10 Error: {e}")
            test_results['tests']['ep10'] = {'status': 'ERROR', 'error': str(e)}
        
        # 11. Overall Assessment
        print(f"\n📋 OVERALL ASSESSMENT:")
        
        passed_tests = sum(1 for test in test_results['tests'].values() if test['status'] == 'PASSED')
        failed_tests = sum(1 for test in test_results['tests'].values() if test['status'] == 'FAILED')
        error_tests = sum(1 for test in test_results['tests'].values() if test['status'] == 'ERROR')
        warning_tests = sum(1 for test in test_results['tests'].values() if test['status'] == 'WARNING')
        
        print(f"✅ Passed: {passed_tests}/10")
        print(f"⚠️ Warnings: {warning_tests}/10")
        print(f"❌ Failed: {failed_tests}/10")
        print(f"🚫 Errors: {error_tests}/10")
        
        if failed_tests == 0 and error_tests == 0:
            test_results['overall_status'] = 'PASSED'
            print(f"\nSUCCESS SYSTEM TEST PASSED - Sistema pronto per ottimizzazione")
        else:
            test_results['overall_status'] = 'FAILED'
            print(f"\nFAILED SYSTEM TEST - Risolvere problemi prima di procedere")
        
        # 12. Salva risultati test
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # Convert date objects to strings for JSON serialization
        json_results = {}
        for key, value in test_results.items():
            if key == 'tests':
                json_results[key] = {}
                for test_key, test_value in value.items():
                    if isinstance(test_value, dict):
                        json_dict = {}
                        for k, v in test_value.items():
                            if isinstance(v, dict):
                                json_dict[k] = {kk: str(vv) if isinstance(vv, datetime) else vv for kk, vv in v.items()}
                            else:
                                json_dict[k] = str(v) if isinstance(v, datetime) else v
                        json_results[key][test_key] = json_dict
                    else:
                        json_results[key][test_key] = test_value
            else:
                json_results[key] = str(value) if isinstance(value, datetime) else value
        
        test_file = os.path.join(reports_dir, f"system_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(test_file, 'w') as f:
            json.dump(json_results, f, indent=2, default=str)
        
        print(f"\nTest results salvati: {test_file}")
        
        return test_results['overall_status'] == 'PASSED'
        
    except Exception as e:
        print(f"ERROR: Errore test completo: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = complete_system_test()
    
    if success:
        print(f"\nSistema pronto per ottimizzazione automatica!")
        print(f"Eseguire: python scripts/auto_strategy_optimizer.py")
    else:
        print(f"\nRisolvere i problemi identificati prima di procedere")
    
    sys.exit(0 if success else 1)
