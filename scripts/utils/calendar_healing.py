#!/usr/bin/env python3
"""
Calendar Healing System - ETF Italia Project v10.8.2

Sistema auto-correttivo per gestione data quality issues attraverso trading calendar.

Principio: Invece di rimuovere dati problematici, li flagghiamo nel calendar.
Il sistema tenta periodicamente il recupero. Se i dati vengono corretti, ripristina automaticamente.

Ciclo: DETECT → FLAG → RETRY → HEAL
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from utils.path_manager import get_path_manager


class CalendarHealing:
    """
    Gestisce il ciclo di vita completo dei quality issues nel trading calendar.
    """
    
    def __init__(self):
        self.pm = get_path_manager()
        self.db_path = str(self.pm.db_path)
        
        # Retry strategy per tipo di issue
        self.retry_config = {
            'zombie_price': {
                'interval_days': 7,
                'max_retry': 3,
                'max_age_days': 30
            },
            'large_gap': {
                'interval_days': 3,
                'max_retry': 2,
                'max_age_days': 10
            },
            'spike': {
                'interval_days': 1,
                'max_retry': 1,
                'max_age_days': 3
            },
            'manual_exclusion': {
                'interval_days': 999,  # Mai retry
                'max_retry': 0,
                'max_age_days': 999
            }
        }
    
    def flag_date(
        self,
        date: str,
        quality_flag: str,
        reason: str,
        symbol: Optional[str] = None,
        venue: str = 'BIT'
    ) -> bool:
        """
        Marca un giorno come problematico nel trading calendar.
        
        Args:
            date: Data da flaggare (YYYY-MM-DD)
            quality_flag: Tipo issue ('zombie_price', 'large_gap', 'spike', 'manual_exclusion')
            reason: Descrizione dettagliata
            symbol: Simbolo coinvolto (opzionale, per logging)
            
        Returns:
            True se flagging riuscito
        """
        conn = duckdb.connect(self.db_path)
        
        try:
            # Verifica che il giorno esista nel calendar
            exists = conn.execute(
                "SELECT COUNT(*) FROM trading_calendar WHERE venue = ? AND date = ?",
                [venue, date]
            ).fetchone()[0]
            
            if not exists:
                print(f"⚠️  Data {date} non esiste in trading_calendar, skip flagging")
                return False
            
            # Flag solo se il giorno è (base) aperto: evita di toccare festivi/weekend
            is_open_row = conn.execute(
                "SELECT is_open FROM trading_calendar WHERE venue = ? AND date = ?",
                [venue, date]
            ).fetchone()

            if not is_open_row:
                print(f"⚠️  Data {date} non trovata per venue={venue}, skip flagging")
                return False

            is_open = bool(is_open_row[0])
            if not is_open:
                print(f"⚠️  Data {date} venue={venue} non è open (holiday/weekend), skip flagging")
                return False

            # Update calendar
            conn.execute("""
                UPDATE trading_calendar
                SET
                    is_open = FALSE,
                    quality_flag = ?,
                    flagged_at = CURRENT_TIMESTAMP,
                    flagged_reason = ?,
                    retry_count = 0,
                    last_retry = NULL,
                    healed_at = NULL
                WHERE venue = ? AND date = ?
            """, [quality_flag, reason, venue, date])
            
            symbol_str = f" ({symbol})" if symbol else ""
            print(f"🚩 FLAGGED: {date}{symbol_str} venue={venue} - {quality_flag}: {reason}")
            return True
            
        except Exception as e:
            print(f"❌ Errore flagging {date}: {e}")
            return False
        finally:
            conn.close()
    
    def should_retry(
        self, 
        date: str, 
        quality_flag: str, 
        retry_count: int,
        flagged_at: datetime,
        last_retry: Optional[datetime]
    ) -> bool:
        """
        Decide se un giorno flaggato deve essere ritentato.
        
        Args:
            date: Data flaggata
            quality_flag: Tipo issue
            retry_count: Numero tentativi già fatti
            flagged_at: Quando è stato flaggato
            last_retry: Ultimo tentativo (None se mai ritentato)
            
        Returns:
            True se deve essere ritentato
        """
        if quality_flag not in self.retry_config:
            return False
        
        config = self.retry_config[quality_flag]
        today = datetime.now()
        
        # Check 1: Max retry raggiunto
        if retry_count >= config['max_retry']:
            return False
        
        # Check 2: Troppo vecchio (accetta come dato reale)
        days_since_flag = (today - flagged_at).days
        if days_since_flag > config['max_age_days']:
            return False
        
        # Check 3: Troppo presto dall'ultimo retry
        if last_retry:
            days_since_retry = (today - last_retry).days
            if days_since_retry < config['interval_days']:
                return False
        else:
            # Primo retry: attendi almeno interval_days
            if days_since_flag < config['interval_days']:
                return False
        
        return True
    
    def get_flagged_dates_for_retry(self, venue: str = 'BIT') -> List[Dict]:
        """
        Ritorna lista di giorni flaggati che devono essere ritentati oggi.
        
        Returns:
            Lista di dict con info giorni da ritentare
        """
        conn = duckdb.connect(self.db_path)
        
        try:
            query = """
            SELECT 
                date,
                quality_flag,
                flagged_at,
                flagged_reason,
                retry_count,
                last_retry
            FROM trading_calendar
            WHERE venue = ?
              AND quality_flag IS NOT NULL
              AND healed_at IS NULL
            ORDER BY flagged_at
            """
            
            df = conn.execute(query, [venue]).df()
            
            retry_list = []
            for _, row in df.iterrows():
                if self.should_retry(
                    date=row['date'],
                    quality_flag=row['quality_flag'],
                    retry_count=row['retry_count'],
                    flagged_at=row['flagged_at'],
                    last_retry=row['last_retry']
                ):
                    retry_list.append({
                        'date': row['date'],
                        'quality_flag': row['quality_flag'],
                        'reason': row['flagged_reason'],
                        'retry_count': row['retry_count'],
                        'venue': venue
                    })
            
            return retry_list
            
        finally:
            conn.close()
    
    def increment_retry_count(self, date: str, venue: str = 'BIT') -> None:
        """
        Incrementa retry_count per un giorno dopo tentativo fallito.
        
        Args:
            date: Data da aggiornare
        """
        conn = duckdb.connect(self.db_path)
        
        try:
            conn.execute("""
                UPDATE trading_calendar
                SET 
                    retry_count = retry_count + 1,
                    last_retry = CURRENT_TIMESTAMP
                WHERE venue = ? AND date = ?
            """, [venue, date])
            
        finally:
            conn.close()
    
    def heal_date(self, date: str, symbol: Optional[str] = None, venue: str = 'BIT') -> bool:
        """
        Ripristina un giorno come trading day dopo healing riuscito.
        
        Args:
            date: Data da ripristinare
            symbol: Simbolo coinvolto (opzionale, per logging)
            
        Returns:
            True se healing riuscito
        """
        conn = duckdb.connect(self.db_path)
        
        try:
            # Verifica che il giorno sia effettivamente flaggato
            flagged = conn.execute(
                """
                SELECT quality_flag
                FROM trading_calendar
                WHERE venue = ? AND date = ? AND quality_flag IS NOT NULL
                """,
                [venue, date]
            ).fetchone()
            
            if not flagged:
                print(f"⚠️  Data {date} non è flaggata, skip healing")
                return False
            
            quality_flag = flagged[0]
            
            # Ripristina
            conn.execute("""
                UPDATE trading_calendar
                SET 
                    is_open = TRUE,
                    quality_flag = NULL,
                    healed_at = CURRENT_TIMESTAMP
                WHERE venue = ? AND date = ?
            """, [venue, date])
            
            symbol_str = f" ({symbol})" if symbol else ""
            print(f"✅ HEALED: {date}{symbol_str} venue={venue} - {quality_flag} risolto")
            return True
            
        except Exception as e:
            print(f"❌ Errore healing {date}: {e}")
            return False
        finally:
            conn.close()
    
    def get_healing_stats(self, venue: str = 'BIT') -> Dict:
        """
        Ritorna statistiche sistema healing.
        
        Returns:
            Dict con statistiche
        """
        conn = duckdb.connect(self.db_path)
        
        try:
            # Giorni attualmente flaggati
            flagged = conn.execute("""
                SELECT 
                    quality_flag,
                    COUNT(*) as count,
                    AVG(retry_count) as avg_retry,
                    MAX(retry_count) as max_retry
                FROM trading_calendar
                WHERE venue = ?
                  AND quality_flag IS NOT NULL
                  AND healed_at IS NULL
                GROUP BY quality_flag
            """, [venue]).df()
            
            # Giorni healed (successi)
            healed = conn.execute("""
                SELECT 
                    quality_flag,
                    COUNT(*) as count,
                    AVG(DATEDIFF('day', flagged_at, healed_at)) as avg_days_to_heal,
                    AVG(retry_count) as avg_retry_to_heal
                FROM trading_calendar
                WHERE venue = ?
                  AND healed_at IS NOT NULL
                GROUP BY quality_flag
            """, [venue]).df()
            
            # Tasso successo
            success_rate = conn.execute("""
                SELECT 
                    quality_flag,
                    COUNT(*) as total,
                    SUM(CASE WHEN healed_at IS NOT NULL THEN 1 ELSE 0 END) as healed,
                    ROUND(100.0 * SUM(CASE WHEN healed_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
                FROM trading_calendar
                WHERE venue = ?
                  AND (quality_flag IS NOT NULL OR healed_at IS NOT NULL)
                GROUP BY quality_flag
            """, [venue]).df()
            
            return {
                'flagged': flagged.to_dict('records'),
                'healed': healed.to_dict('records'),
                'success_rate': success_rate.to_dict('records'),
                'venue': venue,
                'timestamp': datetime.now().isoformat()
            }
            
        finally:
            conn.close()
    
    def print_healing_report(self) -> None:
        """
        Stampa report leggibile dello stato healing system.
        """
        stats = self.get_healing_stats()
        
        print("\n" + "=" * 60)
        print("📊 CALENDAR HEALING SYSTEM - STATUS REPORT")
        print("=" * 60)
        print(f"Timestamp: {stats['timestamp']}")
        
        print("\n🚩 GIORNI ATTUALMENTE FLAGGATI:")
        if stats['flagged']:
            for item in stats['flagged']:
                print(f"   {item['quality_flag']}: {item['count']} giorni "
                      f"(avg retry: {item['avg_retry']:.1f}, max: {item['max_retry']})")
        else:
            print("   ✅ Nessun giorno flaggato")
        
        print("\n✅ GIORNI HEALED (SUCCESSI):")
        if stats['healed']:
            for item in stats['healed']:
                print(f"   {item['quality_flag']}: {item['count']} giorni "
                      f"(avg {item['avg_days_to_heal']:.1f} giorni per heal, "
                      f"{item['avg_retry_to_heal']:.1f} retry)")
        else:
            print("   Nessun healing completato ancora")
        
        print("\n📈 TASSO SUCCESSO:")
        if stats['success_rate']:
            for item in stats['success_rate']:
                if item['quality_flag']:  # Skip NULL
                    print(f"   {item['quality_flag']}: {item['success_rate_pct']}% "
                          f"({item['healed']}/{item['total']})")
        
        print("=" * 60)


def migrate_calendar_schema():
    """
    Aggiunge colonne healing al trading_calendar se non esistono.
    Safe to run multiple times (idempotent).
    """
    pm = get_path_manager()
    conn = duckdb.connect(str(pm.db_path))
    
    print("\n🔧 MIGRAZIONE SCHEMA TRADING_CALENDAR")
    print("=" * 60)
    
    try:
        # Check se colonne già esistono
        columns = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trading_calendar'
        """).df()['column_name'].tolist()
        
        migrations_needed = []
        
        if 'quality_flag' not in columns:
            migrations_needed.append("quality_flag VARCHAR")
        if 'flagged_at' not in columns:
            migrations_needed.append("flagged_at TIMESTAMP")
        if 'flagged_reason' not in columns:
            migrations_needed.append("flagged_reason TEXT")
        if 'retry_count' not in columns:
            migrations_needed.append("retry_count INTEGER DEFAULT 0")
        if 'last_retry' not in columns:
            migrations_needed.append("last_retry TIMESTAMP")
        if 'healed_at' not in columns:
            migrations_needed.append("healed_at TIMESTAMP")
        
        if not migrations_needed:
            print("✅ Schema già aggiornato, nessuna migrazione necessaria")
            return True
        
        print(f"📝 Aggiungo {len(migrations_needed)} colonne...")
        
        for col_def in migrations_needed:
            col_name = col_def.split()[0]
            try:
                conn.execute(f"ALTER TABLE trading_calendar ADD COLUMN {col_def}")
                print(f"   ✅ Aggiunta colonna: {col_name}")
            except Exception as e:
                print(f"   ⚠️  Colonna {col_name} già esiste o errore: {e}")
        
        # Crea indici se non esistono
        try:
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_quality_flag 
                ON trading_calendar(quality_flag) 
                WHERE quality_flag IS NOT NULL
            """)
            print("   ✅ Creato indice: idx_quality_flag")
        except:
            pass
        
        try:
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_retry_pending 
                ON trading_calendar(last_retry, retry_count) 
                WHERE quality_flag IS NOT NULL
            """)
            print("   ✅ Creato indice: idx_retry_pending")
        except:
            pass
        
        print("\n✅ Migrazione completata con successo")
        return True
        
    except Exception as e:
        print(f"\n❌ Errore durante migrazione: {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Calendar Healing System')
    parser.add_argument('--migrate', action='store_true', 
                       help='Esegui migrazione schema')
    parser.add_argument('--stats', action='store_true',
                       help='Mostra statistiche healing')
    parser.add_argument('--retry-list', action='store_true',
                       help='Mostra giorni da ritentare oggi')
    
    args = parser.parse_args()
    
    if args.migrate:
        migrate_calendar_schema()
    
    elif args.stats:
        healer = CalendarHealing()
        healer.print_healing_report()
    
    elif args.retry_list:
        healer = CalendarHealing()
        retry_list = healer.get_flagged_dates_for_retry()
        
        print("\n🔄 GIORNI DA RITENTARE OGGI")
        print("=" * 60)
        
        if retry_list:
            for item in retry_list:
                print(f"   {item['date']} - {item['quality_flag']} "
                      f"(retry #{item['retry_count'] + 1})")
                print(f"      Reason: {item['reason']}")
        else:
            print("   ✅ Nessun giorno da ritentare oggi")
    
    else:
        print("Usa --migrate, --stats o --retry-list")
