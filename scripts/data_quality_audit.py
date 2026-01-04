#!/usr/bin/env python3
"""
Data Quality Audit - ETF Italia Project v10
Verifica completezza, affidabilità e certificazione storico dati 2010+
"""

import sys
import os
import json
import duckdb
import pandas as pd
from datetime import datetime, timedelta
import requests

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def audit_data_quality():
    """Audit completo qualità dati storici"""
    
    print("🔍 DATA QUALITY AUDIT - ETF Italia Project v10")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'etf_data.duckdb')
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'etf_universe.json')
    
    conn = duckdb.connect(db_path)
    
    try:
        # Carica configurazione
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        symbols = []
        symbols.extend([etf['symbol'] for etf in config['universe']['core']])
        symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
        symbols.extend([etf['symbol'] for etf in config['universe']['benchmark']])
        
        print(f"📊 Simboli audit: {symbols}")
        
        # Audit per ogni simbolo
        audit_results = {}
        
        for symbol in symbols:
            print(f"\n📈 AUDIT {symbol}")
            print("-" * 40)
            
            # 1. Completezza storico
            completeness_query = """
            SELECT 
                COUNT(*) as total_records,
                MIN(date) as first_date,
                MAX(date) as last_date,
                COUNT(DISTINCT date) as unique_dates
            FROM market_data 
            WHERE symbol = ?
            """
            
            result = conn.execute(completeness_query, [symbol]).fetchone()
            total_records, first_date, last_date, unique_dates = result
            
            print(f"📅 Periodo: {first_date} → {last_date}")
            print(f"📊 Records: {total_records} totali, {unique_dates} date uniche")
            
            # Verifica copertura 2010+
            if first_date:
                years_since_2010 = datetime.now().year - 2010
                expected_trading_days = years_since_2010 * 252  # ~252 trading days/year
                
                coverage_pct = (unique_dates / expected_trading_days) * 100 if expected_trading_days > 0 else 0
                print(f"📈 Copertura 2010+: {coverage_pct:.1f}% ({unique_dates}/{expected_trading_days} giorni)")
            
            # 2. Affidabilità dati
            quality_query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN adj_close <= 0 OR volume < 0 THEN 1 ELSE 0 END) as zero_issues,
                SUM(CASE WHEN high < low OR high < close OR low > close THEN 1 ELSE 0 END) as consistency_issues,
                AVG(adj_close) as avg_price,
                MIN(adj_close) as min_price,
                MAX(adj_close) as max_price
            FROM market_data 
            WHERE symbol = ?
            """
            
            quality_result = conn.execute(quality_query, [symbol]).fetchone()
            total, zero_issues, consistency_issues, avg_price, min_price, max_price = quality_result
            
            print(f"💰 Range prezzi: €{min_price:.2f} - €{max_price:.2f} (media: €{avg_price:.2f})")
            print(f"⚠️ Issue detection: {zero_issues} zero/negative, {consistency_issues} consistency")
            
            # 3. Gap detection
            gap_query = """
            WITH date_series AS (
                SELECT date, 
                       LAG(date) OVER (ORDER BY date) as prev_date
                FROM market_data 
                WHERE symbol = ?
                ORDER BY date
            )
            SELECT 
                COUNT(*) as total_gaps,
                MAX(DATEDIFF('day', prev_date, date)) as max_gap_days
            FROM date_series 
            WHERE prev_date IS NOT NULL 
              AND DATEDIFF('day', prev_date, date) > 1
            """
            
            gap_result = conn.execute(gap_query, [symbol]).fetchone()
            total_gaps, max_gap_days = gap_result
            
            print(f"🕳️ Data gaps: {total_gaps} gaps, max {max_gap_days} giorni")
            
            # 4. Volume analysis
            volume_query = """
            SELECT 
                COUNT(*) as zero_volume_days,
                AVG(volume) as avg_volume,
                MAX(volume) as max_volume
            FROM market_data 
            WHERE symbol = ? AND volume = 0
            """
            
            vol_result = conn.execute(volume_query, [symbol]).fetchone()
            zero_volume_days, avg_volume, max_volume = vol_result
            
            total_vol_query = "SELECT AVG(volume) as avg_total, MAX(volume) as max_total FROM market_data WHERE symbol = ?"
            total_vol_result = conn.execute(total_vol_query, [symbol]).fetchone()
            avg_total_vol, max_total_vol = total_vol_result
            
            zero_vol_pct = (zero_volume_days / unique_dates * 100) if unique_dates > 0 else 0
            print(f"📊 Volume: {zero_volume_days} giorni zero volume ({zero_vol_pct:.1f}%)")
            print(f"📈 Media volume: {avg_total_vol:,.0f}, max: {max_total_vol:,.0f}")
            
            # 5. Provider source analysis
            source_query = """
            SELECT source, COUNT(*) as count
            FROM market_data 
            WHERE symbol = ?
            GROUP BY source
            """
            
            sources = conn.execute(source_query, [symbol]).fetchall()
            print(f"🔌 Sources: {', '.join([f'{s[0]}({s[1]})' for s in sources])}")
            
            # 6. Certification score
            certification_score = calculate_certification_score(
                total_records, unique_dates, coverage_pct if 'coverage_pct' in locals() else 0,
                zero_issues, consistency_issues, total_gaps, zero_vol_pct
            )
            
            print(f"🏆 Certification Score: {certification_score}/100")
            
            audit_results[symbol] = {
                'period': f"{first_date} → {last_date}",
                'records': total_records,
                'coverage_2010': coverage_pct if 'coverage_pct' in locals() else 0,
                'quality_score': certification_score,
                'issues': {
                    'zero': zero_issues,
                    'consistency': consistency_issues,
                    'gaps': total_gaps,
                    'zero_volume_pct': zero_vol_pct
                }
            }
        
        # Report finale
        print("\n" + "=" * 60)
        print("📋 RIEPILOGO AUDIT COMPLETATO")
        print("=" * 60)
        
        for symbol, results in audit_results.items():
            status = "✅ CERTIFICATO" if results['quality_score'] >= 90 else "⚠️ DA VERIFICARE" if results['quality_score'] >= 70 else "❌ NON CONFORME"
            print(f"{symbol}: {status} (Score: {results['quality_score']}/100)")
            print(f"  Periodo: {results['period']}")
            print(f"  Copertura 2010+: {results['coverage_2010']:.1f}%")
        
        # Raccomandazioni
        print("\n💡 RACCOMANDAZIONI:")
        print("=" * 60)
        
        low_coverage = [s for s, r in audit_results.items() if r['coverage_2010'] < 80]
        if low_coverage:
            print(f"📅 Estendere storico per: {', '.join(low_coverage)}")
        
        high_issues = [s for s, r in audit_results.items() if r['quality_score'] < 80]
        if high_issues:
            print(f"🔧 Investigare problemi per: {', '.join(high_issues)}")
        
        if not low_coverage and not high_issues:
            print("✅ Tutti i simboli conformi - storico affidabile!")
        
        return audit_results
        
    except Exception as e:
        print(f"❌ Errore audit: {e}")
        return {}
        
    finally:
        conn.close()

def calculate_certification_score(records, unique_dates, coverage_pct, zero_issues, consistency_issues, gaps, zero_vol_pct):
    """Calcola score certificazione 0-100"""
    
    score = 100
    
    # Penalties
    if coverage_pct < 90:
        score -= (90 - coverage_pct) * 0.5
    
    if zero_issues > 0:
        score -= min(zero_issues * 2, 10)
    
    if consistency_issues > 0:
        score -= min(consistency_issues * 1, 15)
    
    if gaps > 5:
        score -= min((gaps - 5) * 2, 20)
    
    if zero_vol_pct > 10:
        score -= min(zero_vol_pct, 15)
    
    return max(0, int(score))

if __name__ == "__main__":
    audit_data_quality()
