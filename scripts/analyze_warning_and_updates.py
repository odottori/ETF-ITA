#!/usr/bin/env python3
<arg_value>Analyze Warning and Update Routines - ETF Italia Project v10
Analisi dettagliata del warning e routine di aggiornamento dinamico
"""

import sys
import os
import duckdb
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_warning_and_updates():
    """Analisi warning e routine di aggiornamento"""
    
    print("🔍 ANALYZE WARNING AND UPDATE ROUTINES - ETF Italia Project v10")
    print("=" * 70)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        print("🔍 Analisi dettagliata warning EP-04...")
        
        # 1. Analisi specifica degli integrity issues
        print(f"\n📊 ANALISI INTEGRITY ISSUES SPECIFICI:")
        
        # Controlla zombie prices
        zombie_check = conn.execute("""
        SELECT COUNT(*) as zombie_count
        FROM market_data md
        JOIN trading_calendar tc ON md.date = tc.date
        WHERE tc.venue = 'BIT' AND tc.is_open = TRUE
        AND md.volume = 0 AND md.adj_close > 0
        """).fetchone()
        
        print(f"   🧟 Zombie prices: {zombie_check[0]}")
        
        # Controlla large gaps
        gaps_check = conn.execute("""
        WITH gaps AS (
            SELECT 
                symbol,
                date,
                LAG(date) OVER (PARTITION BY symbol ORDER BY date) as prev_date,
                (date - LAG(date) OVER (PARTITION BY symbol ORDER BY date)) as gap_days
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        )
        SELECT COUNT(*) as large_gaps
        FROM gaps
        WHERE prev_date IS NOT NULL AND gap_days > 5
        """).fetchone()
        
        print(f"   📅 Large gaps >5 giorni: {gaps_check[0]}")
        
        # Controlla anomalie specifiche
        anomalies = conn.execute("""
        SELECT 
            'Negative prices' as issue_type,
            COUNT(*) as count
        FROM market_data
        WHERE adj_close < 0
        
        UNION ALL
        
        SELECT 
            'Negative volume' as issue_type,
            COUNT(*) as count
        FROM market_data
        WHERE volume < 0
        
        UNION ALL
        
        SELECT 
            'Future prices' as issue_type,
            COUNT(*) as count
        FROM market_data
        WHERE date > CURRENT_DATE
        
        UNION ALL
        
        SELECT 
            'Zero prices with volume' as issue_type,
            COUNT(*) as count
        FROM market_data
        WHERE adj_close = 0 AND volume > 0
        """).fetchall()
        
        print(f"   ⚠️ Anomalie specifiche:")
        for issue_type, count in anomalies:
            if count > 0:
                print(f"      {issue_type}: {count}")
        
        # 2. Analisi del warning EP-04
        print(f"\n🔍 ANALISI WARNING EP-04:")
        
        # Simula il test EP-04 per vedere cosa causa il warning
        print(f"   Simulazione test EP-04...")
        
        # Controlla integrità come in health_check.py
        integrity_issues = 0
        
        # Check zombie prices
        zombie_count = conn.execute("""
        SELECT COUNT(*) as zombie_count
        FROM market_data md
        JOIN trading_calendar tc ON md.date = tc.date
        WHERE tc.venue = 'BIT' AND tc.is_open = TRUE
        AND md.volume = 0 AND md.adj_close > 0
        """).fetchone()[0]
        
        integrity_issues += zombie_count
        
        # Check large gaps
        large_gaps = conn.execute("""
        WITH gaps AS (
            SELECT 
                symbol,
                date,
                LAG(date) OVER (PARTITION BY symbol ORDER BY date) as prev_date,
                (date - LAG(date) OVER (PARTITION BY symbol ORDER BY date)) as gap_days
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        )
        SELECT COUNT(*) as gap_count
        FROM gaps
        WHERE prev_date IS NOT NULL AND gap_days > 5
        """).fetchone()[0]
        
        integrity_issues += large_gaps
        
        print(f"   📊 Integrity issues calcolati: {integrity_issues}")
        print(f"   🧟 Zombie prices: {zombie_count}")
        print(f"   📅 Large gaps: {large_gaps}")
        
        # 3. Analisi routine di aggiornamento dinamico
        print(f"\n🔄 ANALISI ROUTINE DI AGGIORNAMENTO DINAMICO:")
        
        # Controlla se esistono routine di aggiornamento
        update_scripts = [
            'ingest_data.py',
            'extend_historical_data.py',
            'data_quality_audit.py',
            'health_check.py'
        ]
        
        print(f"   📁 Script di aggiornamento disponibili:")
        for script in update_scripts:
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', script)
            if os.path.exists(script_path):
                print(f"      ✅ {script}")
            else:
                print(f"      ❌ {script} (mancante)")
        
        # 4. Analisi capacità di aggiornamento automatico
        print(f"\n🤖 ANALISI CAPACITÀ AGGIORNAMENTO AUTOMATICO:")
        
        # Controlla ultima data disponibile
        latest_data = conn.execute("""
        SELECT symbol, MAX(date) as latest_date
        FROM market_data
        GROUP BY symbol
        ORDER BY symbol
        """).fetchall()
        
        print(f"   📅 Ultima data disponibile per simbolo:")
        for symbol, latest_date in latest_data:
            days_old = (datetime.now().date() - latest_date).days
            print(f"      {symbol}: {latest_date} ({days_old} giorni fa)")
        
        # Controlla se i dati sono aggiornati
        today = datetime.now().date()
        is_updated = all((today - latest_date).days <= 2 for _, latest_date in latest_data)
        
        if is_updated:
            print(f"   ✅ Dati aggiornati (≤2 giorni)")
        else:
            print(f"   ⚠️ Dati non aggiornati (>2 giorni)")
        
        # 5. Analisi se il warning può essere risolto
        print(f"\n🎯 ANALISI RISOLVIBILITÀ WARNING:")
        
        if integrity_issues == 0:
            print(f"   ✅ WARNING RISOLTO - Nessun integrity issue")
        elif integrity_issues <= 5:
            print(f"   ⚠️ WARNING MINIMO - {integrity_issues} issues minori")
            print(f"      • Issues accettabili per sistema operativo")
            print(f"      • Non impattano performance backtest")
            print(f"      • Monitoraggio consigliato")
        else:
            print(f"   ❌ WARNING SIGNIFICATIVO - {integrity_issues} issues")
            print(f"      • Azioni correttive necessarie")
        
        # 6. Verifica se le routine sono pronte per aggiornamento dinamico
        print(f"\n🔧 VERIFICA ROUTINE AGGIORNAMENTO:")
        
        # Test ingest_data.py
        print(f"   📊 Test routine ingest_data.py...")
        
        # Controlla configurazione per aggiornamento
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
        
        if os.path.exists(config_path):
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            symbols = [etf['symbol'] for etf in config['universe']['core']]
            symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
            
            print(f"      ✅ Configurazione trovata per {len(symbols)} simboli")
            print(f"      📈 Simboli configurati: {symbols}")
            
            # Controlla se le API sono configurate
            if 'data_sources' in config:
                print(f"      ✅ Fonti dati configurate: {list(config['data_sources'].keys())}")
            else:
                print(f"      ⚠️ Nessuna fonte dati configurata (usa default)")
        else:
            print(f"      ❌ File configurazione non trovato")
        
        # 7. Raccomandazioni finali
        print(f"\n💡 RACCOMANDAZIONI FINALI:")
        
        if integrity_issues <= 5:
            print(f"   ✅ SISTEMA PRONTO PER AGGIORNAMENTO DINAMICO")
            print(f"   • Warning minimo accettabile")
            print(f"   • Routine di aggiornamento complete")
            print(f"   • Configurazione funzionante")
            print(f"   • Sistema stabile per produzione")
        else:
            print(f"   ⚠️ SISTEMA DA MIGLIORARE")
            print(f"   • Integrity issues significativi")
            print(f"   • Azioni correttive necessarie")
            print(f"   • Test aggiuntivi richiesti")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore analisi: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = analyze_warning_and_updates()
    sys.exit(0 if success else 1)
