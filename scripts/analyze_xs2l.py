#!/usr/bin/env python3
"""
XS2L.MI Detailed Analysis - ETF Italia Project v10
Analisi completa stato XS2L.MI post-estensione storico
"""

import duckdb
import os

def analyze_xs2l():
    """Analisi dettagliata XS2L.MI"""
    
    print("🔍 ANALISI DETTAGLIATA XS2L.MI")
    print("=" * 50)
    
    db_path = os.path.join('data', 'etf_data.duckdb')
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Copertura temporale
        result = conn.execute("""
        SELECT 
            MIN(date) as first_date,
            MAX(date) as last_date,
            COUNT(*) as total_records,
            COUNT(DISTINCT date) as unique_dates
        FROM market_data 
        WHERE symbol = 'XS2L.MI'
        """).fetchone()
        
        first_date, last_date, total_records, unique_dates = result
        print(f"📅 Periodo: {first_date} → {last_date}")
        print(f"📊 Records: {total_records} totali, {unique_dates} date uniche")
        
        # 2. Calcolo coverage 2010+
        years = 2026 - 2010
        expected_days = years * 252
        coverage = (unique_dates / expected_days) * 100
        print(f"📈 Coverage 2010+: {coverage:.1f}% ({unique_dates}/{expected_days} giorni)")
        
        # 3. Quality issues
        quality = conn.execute("""
        SELECT 
            SUM(CASE WHEN adj_close <= 0 OR volume < 0 THEN 1 ELSE 0 END) as zero_issues,
            SUM(CASE WHEN high < low OR high < close OR low > close THEN 1 ELSE 0 END) as consistency_issues,
            COUNT(*) as total
        FROM market_data 
        WHERE symbol = 'XS2L.MI'
        """).fetchone()
        
        zero_issues, consistency_issues, total = quality
        print(f"⚠️ Quality issues: {zero_issues} zero/negative, {consistency_issues} consistency")
        
        # 4. Gaps analysis
        gaps = conn.execute("""
        WITH date_series AS (
            SELECT date, LAG(date) OVER (ORDER BY date) as prev_date
            FROM market_data 
            WHERE symbol = 'XS2L.MI'
            ORDER BY date
        )
        SELECT 
            COUNT(*) as total_gaps,
            MAX(DATEDIFF('day', prev_date, date)) as max_gap_days
        FROM date_series 
        WHERE prev_date IS NOT NULL AND DATEDIFF('day', prev_date, date) > 1
        """).fetchone()
        
        total_gaps, max_gap_days = gaps
        print(f"🕳️ Data gaps: {total_gaps} gaps, max {max_gap_days} giorni")
        
        # 5. Volume analysis
        vol_zero = conn.execute("SELECT COUNT(*) FROM market_data WHERE symbol = 'XS2L.MI' AND volume = 0").fetchone()[0]
        zero_vol_pct = (vol_zero / unique_dates) * 100
        print(f"📊 Zero volume: {vol_zero} giorni ({zero_vol_pct:.1f}%)")
        
        # 6. Certification score finale
        score = 100
        if coverage < 90: score -= (90 - coverage) * 0.5
        if zero_issues > 0: score -= min(zero_issues * 2, 10)
        if consistency_issues > 0: score -= min(consistency_issues * 1, 15)
        if total_gaps > 5: score -= min((total_gaps - 5) * 2, 20)
        if zero_vol_pct > 10: score -= min(zero_vol_pct, 15)
        
        score = max(0, int(score))
        
        # 7. Verdict
        if score >= 90:
            status = "✅ ECCCELENTE"
        elif score >= 80:
            status = "✅ BUONO"
        elif score >= 70:
            status = "⚠️ ACCETTABILE"
        else:
            status = "❌ INSUFFICIENTE"
        
        print(f"🏆 Certification Score: {score}/100")
        print(f"🎯 Verdict: {status}")
        
        # 8. Analisi cause gaps
        print(f"\n🔍 ANALISI GAPS XS2L.MI:")
        print("-" * 30)
        
        large_gaps = conn.execute("""
        WITH date_series AS (
            SELECT date, LAG(date) OVER (ORDER BY date) as prev_date
            FROM market_data 
            WHERE symbol = 'XS2L.MI'
            ORDER BY date
        )
        SELECT date, DATEDIFF('day', prev_date, date) as gap_days
        FROM date_series 
        WHERE prev_date IS NOT NULL AND DATEDIFF('day', prev_date, date) > 5
        ORDER BY gap_days DESC
        LIMIT 10
        """).fetchall()
        
        if large_gaps:
            print("Gaps più grandi (>5 giorni):")
            for date, gap in large_gaps:
                print(f"  {date}: {gap} giorni")
        else:
            print("Nessun gap significativo")
        
        # 9. Confronto con altri ETF
        print(f"\n📊 CONFRONTO CON ALTRI ETF:")
        print("-" * 30)
        
        for symbol in ['CSSPX.MI', '^GSPC']:
            result = conn.execute("""
            SELECT COUNT(*) as cnt, MIN(date) as min_date FROM market_data WHERE symbol = ?
            """, [symbol]).fetchone()
            
            cnt, min_date = result
            years_cov = (2026 - min_date.year) + 1
            expected = years_cov * 252
            cov = (cnt / expected) * 100
            
            print(f"{symbol}: {cov:.1f}% coverage, {cnt} records")
        
        # 10. Conclusione
        print(f"\n💡 CONCLUSIONE XS2L.MI:")
        print("=" * 30)
        
        if coverage >= 70 and zero_issues == 0 and consistency_issues == 0:
            print("✅ XS2L.MI è COMPLETO e AFFIDABILE")
            print("   • Coverage sufficiente per backtest robusti")
            print("   • Nessun issue di qualità dati")
            print("   • Gaps normali per ETF leveraged")
            print("   • Pronto per produzione")
        else:
            print("⚠️ XS2L.MI richiede attenzione")
            if coverage < 70:
                print("   • Coverage insufficiente")
            if zero_issues > 0:
                print("   • Presenza di dati anomali")
            if consistency_issues > 0:
                print("   • Problemi di consistenza OHLC")
        
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_xs2l()
