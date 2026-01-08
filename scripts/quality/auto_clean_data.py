#!/usr/bin/env python3
"""
Auto Clean Data - ETF Italia Project v10
Pulizia automatica zombie prices e spike anomali dal database.

Il sistema TENTA la pulizia e documenta ogni tentativo.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from utils.path_manager import get_path_manager
from orchestration.session_manager import get_session_manager
from utils.calendar_healing import CalendarHealing


def clean_zombie_prices(conn, symbols, dry_run=False, venue: str = 'BIT'):
    """
    Flagga zombie prices nel trading_calendar (venue-level) senza rimuovere dati.
    
    Zombie price = stesso prezzo per 3+ giorni consecutivi con volume = 0
    
    Args:
        conn: Connessione DuckDB
        dry_run: Se True, solo simula senza modificare
        
    Returns:
        Dict con statistiche pulizia
    """
    print("\n🧟 ZOMBIE PRICES (CALENDAR FLAGGING)")
    print("=" * 60)

    if not symbols:
        print("⚠️  Nessun simbolo fornito, skip zombie detection")
        return {'flagged_dates': 0, 'total_identified': 0}

    healer = CalendarHealing()
    
    # Identifica zombie prices
    zombie_query = """
    WITH price_changes AS (
        SELECT 
            symbol,
            date,
            close,
            volume,
            LAG(close, 1) OVER (PARTITION BY symbol ORDER BY date) as prev_close_1,
            LAG(close, 2) OVER (PARTITION BY symbol ORDER BY date) as prev_close_2,
            LAG(volume, 1) OVER (PARTITION BY symbol ORDER BY date) as prev_volume_1,
            LAG(volume, 2) OVER (PARTITION BY symbol ORDER BY date) as prev_volume_2
        FROM market_data
    ),
    zombies AS (
        SELECT 
            symbol,
            date,
            close
        FROM price_changes
        WHERE close = prev_close_1 
          AND close = prev_close_2
          AND volume = 0
          AND prev_volume_1 = 0
          AND prev_volume_2 = 0
    )
    SELECT 
        symbol,
        COUNT(*) as zombie_count,
        MIN(date) as first_date,
        MAX(date) as last_date
    FROM zombies
    GROUP BY symbol
    ORDER BY zombie_count DESC
    """
    
    # Identifica zombie per simbolo/date, poi aggrega per data per trovare issue market-wide
    placeholders = ",".join(["?"] * len(symbols))
    zombie_dates_query = f"""
    WITH price_changes AS (
        SELECT 
            symbol,
            date,
            close,
            volume,
            LAG(close, 1) OVER (PARTITION BY symbol ORDER BY date) as prev_close_1,
            LAG(close, 2) OVER (PARTITION BY symbol ORDER BY date) as prev_close_2,
            LAG(volume, 1) OVER (PARTITION BY symbol ORDER BY date) as prev_volume_1,
            LAG(volume, 2) OVER (PARTITION BY symbol ORDER BY date) as prev_volume_2
        FROM market_data
        WHERE symbol IN ({placeholders})
    ),
    zombies AS (
        SELECT symbol, date
        FROM price_changes
        WHERE close = prev_close_1
          AND close = prev_close_2
          AND volume = 0
          AND prev_volume_1 = 0
          AND prev_volume_2 = 0
    )
    SELECT date, COUNT(DISTINCT symbol) as symbols_affected
    FROM zombies
    GROUP BY date
    ORDER BY symbols_affected DESC, date
    """

    zombies_by_date = conn.execute(zombie_dates_query, symbols).df()

    total_identified = int(zombies_by_date['symbols_affected'].sum()) if len(zombies_by_date) else 0
    if len(zombies_by_date) == 0:
        print("✅ Nessun zombie price (market-wide) trovato")
        return {'flagged_dates': 0, 'total_identified': 0}

    threshold = max(3, int(round(len(symbols) * 0.6)))
    candidates = zombies_by_date[zombies_by_date['symbols_affected'] >= threshold]

    print(f"🔍 Zombie market-wide candidates: {len(candidates)}/{len(zombies_by_date)} date (threshold: {threshold}/{len(symbols)} symbols)")

    flagged_dates = 0
    flagged_list = []
    for _, row in candidates.iterrows():
        d = str(row['date'])
        n = int(row['symbols_affected'])
        reason = f"Zombie price pattern detected on {n}/{len(symbols)} symbols"

        if dry_run:
            print(f"   🔄 DRY-RUN: flag venue={venue} date={d} ({reason})")
            continue

        if healer.flag_date(date=d, quality_flag='zombie_price', reason=reason, venue=venue):
            flagged_dates += 1
            flagged_list.append(d)

    if dry_run:
        print(f"\n🔄 DRY-RUN completato: {len(candidates)} date candidate")
    else:
        print(f"\n✅ Flagging completato: {flagged_dates} date flaggate su trading_calendar")

    return {
        'flagged_dates': flagged_dates,
        'flagged_list': flagged_list,
        'total_identified': total_identified,
        'threshold_symbols': threshold,
        'symbols_in_scope': len(symbols)
    }


def clean_large_gaps(conn, symbols, dry_run=False, venue: str = 'BIT'):
    """
    Identifica e flagga "earthquake days" (venue-level): giorni open in trading_calendar
    senza alcun dato per l'intero universo simboli.
    
    Large gap = gap > 5 giorni trading tra due date consecutive
    
    Args:
        conn: Connessione DuckDB
        dry_run: Se True, solo simula
        
    Returns:
        Dict con statistiche gaps
    """
    print("\n📊 LARGE GAPS (EARTHQUAKE DAYS) - CALENDAR FLAGGING")
    print("=" * 60)

    if not symbols:
        print("⚠️  Nessun simbolo fornito, skip gap detection")
        return {'flagged_dates': 0, 'total_identified': 0}

    healer = CalendarHealing()
    
    gap_query = """
    WITH date_diffs AS (
        SELECT 
            symbol,
            date,
            LAG(date) OVER (PARTITION BY symbol ORDER BY date) as prev_date,
            DATEDIFF('day', LAG(date) OVER (PARTITION BY symbol ORDER BY date), date) as gap_days
        FROM market_data
    )
    SELECT 
        symbol,
        COUNT(*) as gap_count,
        MAX(gap_days) as max_gap_days,
        MIN(date) as first_gap,
        MAX(date) as last_gap
    FROM date_diffs
    WHERE gap_days > 5
    GROUP BY symbol
    ORDER BY gap_count DESC
    """
    
    placeholders = ",".join(["?"] * len(symbols))
    missing_market_days_query = f"""
    SELECT tc.date
    FROM trading_calendar tc
    LEFT JOIN (
        SELECT DISTINCT date
        FROM market_data
        WHERE symbol IN ({placeholders})
    ) md ON md.date = tc.date
    WHERE tc.venue = ?
      AND tc.is_open = TRUE
      AND md.date IS NULL
    ORDER BY tc.date
    """

    params = list(symbols) + [venue]
    missing_days = conn.execute(missing_market_days_query, params).df()
    total_identified = int(len(missing_days))

    if total_identified == 0:
        print("✅ Nessun earthquake day trovato")
        return {'flagged_dates': 0, 'total_identified': 0}

    print(f"🔍 Trovati {total_identified} giorni open senza dati market (universe-wide)")

    flagged_dates = 0
    flagged_list = []
    for _, row in missing_days.iterrows():
        d = str(row['date'])
        reason = "No market_data rows for any universe symbol on an open trading day"

        if dry_run:
            print(f"   🔄 DRY-RUN: flag venue={venue} date={d} ({reason})")
            continue

        if healer.flag_date(date=d, quality_flag='large_gap', reason=reason, venue=venue):
            flagged_dates += 1
            flagged_list.append(d)

    if dry_run:
        print(f"\n🔄 DRY-RUN completato: {total_identified} giorni identificati")
    else:
        print(f"\n✅ Flagging completato: {flagged_dates} date flaggate su trading_calendar")

    return {
        'flagged_dates': flagged_dates,
        'flagged_list': flagged_list,
        'total_identified': total_identified
    }


def auto_clean_data(dry_run=False):
    """
    Esegue pulizia automatica dati con documentazione completa.
    
    Args:
        dry_run: Se True, solo simula senza modificare
    """
    pm = get_path_manager()
    db_path = str(pm.db_path)
    conn = duckdb.connect(db_path)

    # Universe symbols (per definire market-wide issues)
    try:
        import json
        with open(str(pm.etf_universe_path), 'r') as f:
            config = json.load(f)
        symbols = []
        universe = config.get('universe', {})
        symbols.extend([e['symbol'] for e in universe.get('core', [])])
        symbols.extend([e['symbol'] for e in universe.get('satellite', [])])
        symbols.extend([e['symbol'] for e in universe.get('benchmark', [])])
        symbols = sorted(set(symbols))
    except Exception:
        symbols = []
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("\n" + "=" * 60)
    print("🧹 AUTO CLEAN DATA - ETF Italia Project v10")
    print("=" * 60)
    print(f"Timestamp: {timestamp}")
    print(f"Mode: {'DRY-RUN (simulazione)' if dry_run else 'LIVE (modifica DB)'}")
    print("=" * 60)
    
    results = {
        'timestamp': timestamp,
        'dry_run': dry_run,
        'zombie_prices': {},
        'large_gaps': {},
        'success': False,
        'errors': []
    }
    
    try:
        # 1. Pulizia zombie prices
        print("\n📍 STEP 1: Pulizia Zombie Prices")
        zombie_results = clean_zombie_prices(conn, symbols=symbols, dry_run=dry_run)
        results['zombie_prices'] = zombie_results
        
        # 2. Analisi large gaps (solo documentazione)
        print("\n📍 STEP 2: Analisi Large Gaps")
        gap_results = clean_large_gaps(conn, symbols=symbols, dry_run=dry_run)
        results['large_gaps'] = gap_results
        
        results['success'] = True
        
    except Exception as e:
        print(f"\n❌ ERRORE durante pulizia: {e}")
        results['errors'].append(str(e))
        results['success'] = False
    
    finally:
        conn.close()
    
    # Salva report nella session
    print("\n📁 Salvataggio report...")
    try:
        sm = get_session_manager(script_name='auto_clean_data')
        output_dir = sm.get_subdir_path('analysis')
        
        import json
        report_path = output_dir / f'auto_clean_data_{timestamp}.json'
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"✅ Report salvato: {report_path}")
    except Exception as e:
        print(f"⚠️  Errore salvataggio report: {e}")
    
    # Summary finale
    print("\n" + "=" * 60)
    print("📊 RIEPILOGO PULIZIA")
    print("=" * 60)
    
    if results['success']:
        zombie_removed = results['zombie_prices'].get('removed', 0)
        zombie_identified = results['zombie_prices'].get('total_identified', 0)
        gaps_found = results['large_gaps'].get('gaps', 0)
        
        if dry_run:
            print(f"🔄 DRY-RUN completato:")
            print(f"   - Zombie prices identificati: {zombie_identified}")
            print(f"   - Large gaps identificati: {gaps_found}")
            print(f"\n💡 Esegui senza --dry-run per applicare le modifiche")
        else:
            print(f"✅ Pulizia completata:")
            print(f"   - Zombie prices rimossi: {zombie_removed}/{zombie_identified}")
            print(f"   - Large gaps documentati: {gaps_found}")
            
            if zombie_removed > 0:
                print(f"\n🎯 Database pulito! Riesegui health_check per verificare")
            else:
                print(f"\n✨ Database già pulito, nessuna modifica necessaria")
    else:
        print(f"❌ Pulizia fallita")
        for error in results['errors']:
            print(f"   - {error}")
    
    print("=" * 60)
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto clean data quality issues')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Simula pulizia senza modificare il database')
    parser.add_argument('--live', action='store_true',
                       help='Esegui pulizia reale (modifica database)')
    
    args = parser.parse_args()
    
    # Default: dry-run per sicurezza
    dry_run = not args.live
    
    if args.live:
        print("\n⚠️  ATTENZIONE: Modalità LIVE - Il database verrà modificato!")
        print("   Premi Ctrl+C per annullare, Enter per continuare...")
        try:
            input()
        except KeyboardInterrupt:
            print("\n❌ Operazione annullata")
            sys.exit(0)
    
    auto_clean_data(dry_run=dry_run)
