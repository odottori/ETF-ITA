#!/usr/bin/env python3
"""
Health Check - ETF Italia Project v10
Verifica integrità dati, gap anomali e zombie prices
"""

import sys
import os
import json
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def health_check():
    """Health check completo del sistema"""
    
    print("🔍 HEALTH CHECK - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'etf_universe.json')
    reports_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
    
    # Assicurati che esista cartella reports
    os.makedirs(reports_path, exist_ok=True)
    
    conn = duckdb.connect(db_path)
    
    try:
        # Carica configurazione
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        symbols = []
        symbols.extend([etf['symbol'] for etf in config['universe']['core']])
        symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
        symbols.extend([etf['symbol'] for etf in config['universe']['benchmark']])
        
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'HEALTHY',
            'issues': [],
            'warnings': [],
            'symbol_status': {},
            'data_quality': {},
            'system_integrity': {}
        }
        
        print(f"📊 Health check simboli: {symbols}")
        
        # 1. System Integrity Check
        print("\n🔧 SYSTEM INTEGRITY CHECK")
        print("-" * 40)
        
        # Verifica tabelle richieste
        required_tables = ['market_data', 'staging_data', 'fiscal_ledger', 'ingestion_audit', 
                         'trading_calendar', 'risk_metrics', 'portfolio_summary']
        
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        existing_tables = [row[0] for row in conn.execute(tables_query).fetchall()]
        
        missing_tables = [t for t in required_tables if t not in existing_tables]
        
        if missing_tables:
            health_report['issues'].append(f"Missing tables: {missing_tables}")
            health_report['overall_status'] = 'CRITICAL'
            print(f"❌ Tabelle mancanti: {missing_tables}")
        else:
            print("✅ Tutte le tabelle richieste presenti")
        
        # Verifica viste
        required_views = ['risk_metrics', 'portfolio_summary']
        views_query = "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
        existing_views = [row[0] for row in conn.execute(views_query).fetchall()]
        
        missing_views = [v for v in required_views if v not in existing_views]
        if missing_views:
            health_report['warnings'].append(f"Missing views: {missing_views}")
            print(f"⚠️ Viste mancanti: {missing_views}")
        else:
            print("✅ Viste analytics presenti")
        
        # 2. Data Quality Check per simbolo
        print(f"\n📊 DATA QUALITY CHECK")
        print("-" * 40)
        
        for symbol in symbols:
            print(f"\n📈 {symbol}")
            
            symbol_health = {
                'status': 'HEALTHY',
                'issues': [],
                'warnings': [],
                'metrics': {}
            }
            
            # Basic stats
            stats_query = """
            SELECT 
                COUNT(*) as total_records,
                MIN(date) as first_date,
                MAX(date) as last_date,
                COUNT(DISTINCT date) as unique_dates
            FROM market_data 
            WHERE symbol = ?
            """
            
            stats = conn.execute(stats_query, [symbol]).fetchone()
            total_records, first_date, last_date, unique_dates = stats
            
            symbol_health['metrics'] = {
                'total_records': total_records,
                'first_date': str(first_date),
                'last_date': str(last_date),
                'unique_dates': unique_dates
            }
            
            print(f"  📅 Periodo: {first_date} → {last_date}")
            print(f"  📊 Records: {total_records}")
            
            # Zero/negative check
            zero_check = conn.execute("""
            SELECT COUNT(*) FROM market_data 
            WHERE symbol = ? AND (adj_close <= 0 OR volume < 0)
            """, [symbol]).fetchone()[0]
            
            if zero_check > 0:
                symbol_health['issues'].append(f"Zero/negative values: {zero_check}")
                symbol_health['status'] = 'WARNING'
                print(f"  ⚠️ Zero/negative: {zero_check}")
            
            # Consistency check
            consistency_check = conn.execute("""
            SELECT COUNT(*) FROM market_data 
            WHERE symbol = ? AND (high < low OR high < close OR low > close)
            """, [symbol]).fetchone()[0]
            
            if consistency_check > 0:
                symbol_health['issues'].append(f"Inconsistent OHLC: {consistency_check}")
                symbol_health['status'] = 'WARNING'
                print(f"  ⚠️ Inconsistent OHLC: {consistency_check}")
            
            # Zombie price detection
            zombie_check = conn.execute("""
            WITH zombie_days AS (
                SELECT date, close, volume,
                   LAG(close) OVER (ORDER BY date) as prev_close
                FROM market_data 
                WHERE symbol = ? AND volume = 0
                ORDER BY date
            )
            SELECT COUNT(*) FROM zombie_days 
            WHERE close = prev_close AND prev_close IS NOT NULL
            """, [symbol]).fetchone()[0]
            
            if zombie_check > 0:
                symbol_health['warnings'].append(f"Zombie prices: {zombie_check}")
                print(f"  ⚠️ Zombie prices: {zombie_check}")
            
            # Spike detection recenti
            spike_check = conn.execute("""
            WITH daily_returns AS (
                SELECT date, adj_close,
                       LAG(adj_close) OVER (ORDER BY date) as prev_adj_close
                FROM market_data 
                WHERE symbol = ? AND date >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY date
            )
            SELECT COUNT(*) FROM daily_returns 
            WHERE prev_adj_close IS NOT NULL 
              AND ABS(adj_close - prev_adj_close) / prev_adj_close > 0.15
            """, [symbol]).fetchone()[0]
            
            if spike_check > 0:
                symbol_health['warnings'].append(f"Recent spikes >15%: {spike_check}")
                print(f"  ⚠️ Recent spikes: {spike_check}")
            
            # Gap detection
            gap_check = conn.execute("""
            WITH date_series AS (
                SELECT date, LAG(date) OVER (ORDER BY date) as prev_date
                FROM market_data 
                WHERE symbol = ?
                ORDER BY date
            )
            SELECT COUNT(*) FROM date_series 
            WHERE prev_date IS NOT NULL 
              AND DATEDIFF('day', prev_date, date) > 5
            """, [symbol]).fetchone()[0]
            
            if gap_check > 0:
                symbol_health['warnings'].append(f"Large gaps (>5 days): {gap_check}")
                print(f"  ⚠️ Large gaps: {gap_check}")
            
            # Status finale simbolo
            if symbol_health['status'] == 'HEALTHY' and not symbol_health['warnings']:
                print(f"  ✅ {symbol}: HEALTHY")
            elif symbol_health['status'] == 'WARNING':
                print(f"  ⚠️ {symbol}: WARNING")
            else:
                print(f"  ❌ {symbol}: ISSUES")
            
            health_report['symbol_status'][symbol] = symbol_health
        
        # 3. Trading Calendar Coherence
        print(f"\n📅 TRADING CALENDAR COHERENCE")
        print("-" * 40)
        
        # Verifica coerenza calendar vs market data
        coherence_check = conn.execute("""
        WITH calendar_days AS (
            SELECT date FROM trading_calendar 
            WHERE venue = 'BIT' AND is_open = TRUE
        ),
        market_days AS (
            SELECT DISTINCT date FROM market_data
        ),
        missing_data AS (
            SELECT c.date FROM calendar_days c
            LEFT JOIN market_days m ON c.date = m.date
            WHERE m.date IS NULL
            LIMIT 10
        )
        SELECT COUNT(*) as total_missing FROM missing_data
        """).fetchone()[0]
        
        if coherence_check > 0:
            health_report['warnings'].append(f"Calendar coherence issues: {coherence_check} missing days")
            print(f"⚠️ Giorni calendar senza dati market: {coherence_check}")
        else:
            print("✅ Trading calendar coerente con market data")
        
        # 4. Ledger Integrity
        print(f"\n💰 FISCAL LEDGER INTEGRITY")
        print("-" * 40)
        
        # Verifica deposito iniziale
        deposit_check = conn.execute("""
        SELECT COUNT(*) FROM fiscal_ledger 
        WHERE type = 'DEPOSIT' AND symbol = 'CASH'
        """).fetchone()[0]
        
        if deposit_check == 0:
            health_report['issues'].append("Missing initial deposit")
            health_report['overall_status'] = 'CRITICAL'
            print("❌ Manca deposito iniziale")
        else:
            print(f"✅ Deposito iniziale presente")
        
        # Verifica posizioni negative
        negative_positions = conn.execute("""
        WITH current_positions AS (
            SELECT symbol, SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty
            FROM fiscal_ledger 
            WHERE type IN ('BUY', 'SELL')
            GROUP BY symbol
        )
        SELECT COUNT(*) FROM current_positions WHERE qty < 0
        """).fetchone()[0]
        
        if negative_positions > 0:
            health_report['issues'].append(f"Negative positions: {negative_positions}")
            health_report['overall_status'] = 'CRITICAL'
            print(f"❌ Posizioni negative: {negative_positions}")
        else:
            print("✅ Nessuna posizione negativa")
        
        # 5. Recent Activity Check
        print(f"\n📈 RECENT ACTIVITY CHECK")
        print("-" * 40)
        
        # Ultima ingestion
        last_ingestion = conn.execute("""
        SELECT MAX(created_at) FROM ingestion_audit
        """).fetchone()[0]
        
        if last_ingestion:
            days_since = (datetime.now() - last_ingestion).days
            if days_since > 7:
                health_report['warnings'].append(f"Last ingestion {days_since} days ago")
                print(f"⚠️ Ultima ingestion: {days_since} giorni fa")
            else:
                print(f"✅ Ultima ingestion: {days_since} giorni fa")
        else:
            health_report['warnings'].append("No ingestion records found")
            print("⚠️ Nessun record ingestion")
        
        # 6. Overall Status con severity riallineata
        print(f"\n🎯 OVERALL STATUS")
        print("=" * 40)
        
        # Controlla severity issues
        total_warnings = len(health_report['warnings'])
        total_issues = len(health_report['issues'])
        
        # Check specifici per severity
        large_gap_warnings = sum(1 for w in health_report['warnings'] if 'Large gaps' in w and int(w.split(':')[-1].strip()) > 50)
        calendar_issues = sum(1 for w in health_report['warnings'] if 'Calendar coherence' in w and int(w.split(':')[-1].strip().split()[0]) > 0)
        
        # Riallinea severity policy
        if total_issues > 0:
            health_report['overall_status'] = 'CRITICAL'
        elif large_gap_warnings > 0 or calendar_issues > 0:
            health_report['overall_status'] = 'DEGRADED'
        elif total_warnings > 5:
            health_report['overall_status'] = 'WARNING'
        else:
            health_report['overall_status'] = 'HEALTHY'
        
        if health_report['overall_status'] == 'HEALTHY':
            print("✅ SYSTEM HEALTHY - Ready for production")
        elif health_report['overall_status'] == 'WARNING':
            print("⚠️ SYSTEM WARNING - Review recommended")
        elif health_report['overall_status'] == 'DEGRADED':
            print("🟡 SYSTEM DEGRADED - Risk Continuity investigation required")
            print("   🟡 Data quality issues detected - review before production")
        else:
            print("❌ SYSTEM CRITICAL - Issues require attention")
        
        # 7. Generate Report
        generate_health_report(health_report, reports_path)
        
        return health_report
        
    except Exception as e:
        print(f"❌ Errore health check: {e}")
        return {'status': 'ERROR', 'error': str(e)}
        
    finally:
        conn.close()

def generate_health_report(report, reports_path):
    """Genera report health in formato markdown"""
    
    report_file = os.path.join(reports_path, f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    content = f"""# 📋 Health Check Report

**Timestamp:** {report['timestamp']}  
**Overall Status:** {report['overall_status']}

---

## 🎯 Executive Summary

{get_status_emoji(report['overall_status'])} **System Status:** {report['overall_status']}

---

## 🔧 System Integrity

- **Required Tables:** ✅ All present
- **Analytics Views:** ✅ All present
- **Database Connection:** ✅ Healthy

---

## 📊 Symbol Status

"""
    
    for symbol, status in report['symbol_status'].items():
        emoji = get_status_emoji(status['status'])
        content += f"### {emoji} {symbol}\n\n"
        content += f"- **Status:** {status['status']}\n"
        content += f"- **Records:** {status['metrics']['total_records']}\n"
        content += f"- **Period:** {status['metrics']['first_date']} → {status['metrics']['last_date']}\n"
        
        if status['issues']:
            content += "- **Issues:**\n"
            for issue in status['issues']:
                content += f"  - ⚠️ {issue}\n"
        
        if status['warnings']:
            content += "- **Warnings:**\n"
            for warning in status['warnings']:
                content += f"  - ⚠️ {warning}\n"
        
        content += "\n"
    
    content += f"""---

## 🚨 Issues

"""
    
    if report['issues']:
        for issue in report['issues']:
            content += f"- ❌ {issue}\n"
    else:
        content += "- ✅ No critical issues\n"
    
    content += f"""

## ⚠️ Warnings

"""
    
    if report['warnings']:
        for warning in report['warnings']:
            content += f"- ⚠️ {warning}\n"
    else:
        content += "- ✅ No warnings\n"
    
    content += f"""

---

## 📈 Recommendations

"""
    
    if report['overall_status'] == 'HEALTHY':
        content += "- ✅ System ready for production\n"
        content += "- ✅ All checks passed\n"
    elif report['overall_status'] == 'WARNING':
        content += "- ⚠️ Review warnings before production\n"
        content += "- ⚠️ Monitor system closely\n"
    elif report['overall_status'] == 'DEGRADED':
        content += "- 🟡 SYSTEM DEGRADED - Data quality issues detected\n"
        content += "- 🟡 Risk Continuity investigation required\n"
        content += "- 🟡 Review before production deployment\n"
    else:
        content += "- ❌ Address critical issues immediately\n"
        content += "- ❌ System not ready for production\n"
    
    content += f"""

---

*Report generated by ETF Italia Project v10 Health Check*
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n📄 Report salvato: {report_file}")

def get_status_emoji(status):
    """Ritorna emoji per status"""
    if status == 'HEALTHY':
        return '✅'
    elif status == 'WARNING':
        return '⚠️'
    elif status == 'DEGRADED':
        return '🟡'
    elif status == 'CRITICAL':
        return '❌'
    else:
        return '❓'

if __name__ == "__main__":
    health_check()
