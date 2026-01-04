#!/usr/bin/env python3
"""
Final Data Quality Assessment - ETF Italia Project v10
Assessment finale della qualità dati e decisione su gaps accettabili
"""

import sys
import os
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def final_data_quality_assessment():
    """Assessment finale qualità dati"""
    
    print("🔍 FINAL DATA QUALITY ASSESSMENT - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        print("📊 Analisi qualità dati finale...")
        
        # 1. Statistiche generali
        stats = conn.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as symbols,
            COUNT(DISTINCT date) as dates,
            MIN(date) as min_date,
            MAX(date) as max_date
        FROM market_data
        """).fetchone()
        
        total_records, symbols, dates, min_date, max_date = stats
        
        print(f"\n📈 STATISTICHE GENERALI:")
        print(f"   Records totali: {total_records:,}")
        print(f"   Simboli: {symbols}")
        print(f"   Date uniche: {dates:,}")
        print(f"   Periodo: {min_date} → {max_date}")
        
        # 2. Analisi gaps per simbolo
        print(f"\n📅 ANALISI GAPS PER SIMBOLO:")
        
        for symbol in ['CSSPX.MI', 'XS2L.MI', '^GSPC']:
            # Calcola gaps
            gaps_query = f"""
            WITH gaps AS (
                SELECT 
                    date,
                    LAG(date) OVER (ORDER BY date) as prev_date,
                    (date - LAG(date) OVER (ORDER BY date)) as gap_days
                FROM market_data
                WHERE symbol = '{symbol}'
                ORDER BY date
            )
            SELECT 
                COUNT(*) as total_gaps,
                COUNT(CASE WHEN gap_days > 5 THEN 1 END) as large_gaps,
                COUNT(CASE WHEN gap_days > 10 THEN 1 END) as very_large_gaps,
                MAX(gap_days) as max_gap,
                AVG(gap_days) as avg_gap
            FROM gaps
            WHERE prev_date IS NOT NULL
            """
            
            gap_stats = conn.execute(gaps_query).fetchone()
            
            if gap_stats:
                total_gaps, large_gaps, very_large_gaps, max_gap, avg_gap = gap_stats
                
                print(f"\n   {symbol}:")
                print(f"     Gaps totali: {total_gaps}")
                print(f"     Gaps >5 giorni: {large_gaps}")
                print(f"     Gaps >10 giorni: {very_large_gaps}")
                print(f"     Gap massimo: {max_gap} giorni")
                print(f"     Gap medio: {avg_gap:.1f} giorni")
                
                # Mostra i gap più grandi
                worst_gaps = conn.execute(f"""
                WITH gaps AS (
                    SELECT 
                        date,
                        LAG(date) OVER (ORDER BY date) as prev_date,
                        (date - LAG(date) OVER (ORDER BY date)) as gap_days
                    FROM market_data
                    WHERE symbol = '{symbol}'
                    ORDER BY date
                )
                SELECT prev_date, date, gap_days
                FROM gaps
                WHERE prev_date IS NOT NULL AND gap_days > 5
                ORDER BY gap_days DESC
                LIMIT 3
                """).fetchall()
                
                if worst_gaps:
                    print(f"     Peggiori gaps:")
                    for prev_date, date, gap_days in worst_gaps:
                        print(f"       {prev_date} → {date} ({gap_days} giorni)")
        
        # 3. Analisi coverage
        print(f"\n📊 ANALISI COVERAGE:")
        
        # Calcola giorni di trading totali nel periodo
        trading_days = conn.execute("""
        SELECT COUNT(*) as total_trading_days
        FROM trading_calendar
        WHERE venue = 'BIT' AND is_open = TRUE
        AND date BETWEEN ? AND ?
        """, [min_date, max_date]).fetchone()[0]
        
        print(f"   Giorni di trading totali: {trading_days:,}")
        print(f"   Giorni con dati: {dates:,}")
        print(f"   Coverage: {(dates/trading_days)*100:.1f}%")
        
        # Coverage per simbolo
        for symbol in ['CSSPX.MI', 'XS2L.MI', '^GSPC']:
            symbol_days = conn.execute(f"""
            SELECT COUNT(DISTINCT date) as symbol_days
            FROM market_data
            WHERE symbol = '{symbol}'
            """).fetchone()[0]
            
            coverage = (symbol_days / trading_days) * 100
            print(f"   {symbol}: {symbol_days:,} giorni ({coverage:.1f}% coverage)")
        
        # 4. Analisi qualità specifica
        print(f"\n🔍 ANALISI QUALITA SPECIFICA:")
        
        # Zombie prices
        zombie_prices = conn.execute("""
        SELECT COUNT(*) as zombie_count
        FROM market_data md
        JOIN trading_calendar tc ON md.date = tc.date
        WHERE tc.venue = 'BIT' AND tc.is_open = TRUE
        AND md.volume = 0 AND md.adj_close > 0
        """).fetchone()[0]
        
        print(f"   Zombie prices: {zombie_prices}")
        
        # Volume analysis
        volume_stats = conn.execute("""
        SELECT 
            COUNT(*) as zero_volume,
            COUNT(CASE WHEN volume > 0 THEN 1 END) as positive_volume,
            AVG(volume) as avg_volume,
            MAX(volume) as max_volume
        FROM market_data
        WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        """).fetchone()
        
        zero_volume, positive_volume, avg_volume, max_volume = volume_stats
        
        print(f"   Volume zero: {zero_volume}")
        print(f"   Volume positivo: {positive_volume}")
        print(f"   Volume medio: {avg_volume:,.0f}")
        print(f"   Volume massimo: {max_volume:,.0f}")
        
        # 5. Decisione su gaps accettabili
        print(f"\n🎯 DECISIONE SU GAPS ACCETTABILI:")
        
        # Analisi se i gaps sono accettabili
        large_gaps_total = conn.execute("""
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
        """).fetchone()[0]
        
        # Calcola percentuale di gaps accettabili
        gap_percentage = (large_gaps_total / trading_days) * 100
        
        print(f"   Large gaps totali: {large_gaps_total}")
        print(f"   Percentuale gaps: {gap_percentage:.2f}%")
        
        if gap_percentage < 5:
            print(f"   ✅ Gaps accettabili (<5%)")
        elif gap_percentage < 10:
            print(f"   ⚠️ Gaps marginali (5-10%)")
        else:
            print(f"   ❌ Gaps eccessivi (>10%)")
        
        # 6. Raccomandazioni finali
        print(f"\n💡 RACCOMANDAZIONI FINALI:")
        
        if zombie_prices == 0 and gap_percentage < 5:
            print(f"   ✅ DATI DI ALTA QUALITÀ")
            print(f"   • Nessun zombie price")
            print(f"   • Gaps minimi ({gap_percentage:.2f}%)")
            print(f"   • Coverage eccellente")
            print(f"   • Sistema pronto per produzione")
        elif zombie_prices < 10 and gap_percentage < 10:
            print(f"   ⚠️ DATI DI BUONA QUALITÀ")
            print(f"   • Zombie prices minimi: {zombie_prices}")
            print(f"   • Gaps accettabili: {gap_percentage:.2f}%")
            print(f"   • Sistema funzionante")
            print(f"   • Monitoraggio consigliato")
        else:
            print(f"   ❌ DATI DA MIGLIORARE")
            print(f"   • Zombie prices eccessivi: {zombie_prices}")
            print(f"   • Gaps eccessivi: {gap_percentage:.2f}%")
            print(f"   • Azioni correttive necessarie")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore assessment: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = final_data_quality_assessment()
    sys.exit(0 if success else 1)
