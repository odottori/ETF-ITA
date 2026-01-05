#!/usr/bin/env python3
"""
Load Trading Calendar - ETF Italia Project v10
Carica calendario di trading per borse italiane (BIT)
"""

import sys
import os
import argparse
import duckdb
from datetime import datetime, date

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_trading_calendar(venue='BIT', csv_file=None):
    """Carica calendario trading da CSV o genera base"""
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    conn = duckdb.connect(db_path)
    
    try:
        print(f" Caricamento trading calendar per {venue}")
        
        if csv_file and os.path.exists(csv_file):
            print(f" Caricamento da CSV: {csv_file}")
            
            # Carica da CSV (formato: date,is_open)
            conn.execute(f"""
            COPY trading_calendar(venue, date, is_open)
            FROM '{csv_file}'
            (AUTO_DETECT TRUE, HEADER TRUE)
            """)
            
            print(f" Calendario caricato da {csv_file}")
            
        else:
            print(" Generazione calendario base (giorni feriali)")
            
            # Genera calendario base per anni 2020-2026 (P0.1)
            start_date = '2020-01-01'
            end_date = '2026-12-31'  # Esteso a 2026 per production readiness
            
            # Pulisci dati esistenti per questo venue
            conn.execute("DELETE FROM trading_calendar WHERE venue = ?", [venue])
            
            # Inserisci giorni feriali (lunedì-venerdì)
            conn.execute(f"""
            INSERT INTO trading_calendar (venue, date, is_open)
            SELECT '{venue}',
                   generate_series::date,
                   EXTRACT(ISODOW FROM generate_series::date) NOT IN (6, 7) as is_open
            FROM generate_series('{start_date}'::DATE, '{end_date}'::DATE, INTERVAL '1 day')
            """)
            
            # Aggiungi alcuni festivi italiani principali
            italian_holidays = [
                ('2020-01-01', 'Capodanno'),
                ('2020-01-06', 'Epifania'),
                ('2020-04-12', 'Pasqua'),
                ('2020-04-13', 'Pasquetta'),
                ('2020-04-25', 'Liberazione'),
                ('2020-05-01', 'Lavoro'),
                ('2020-06-02', 'Repubblica'),
                ('2020-08-15', 'Ferragosto'),
                ('2020-11-01', 'Ognissanti'),
                ('2020-12-08', 'Immacolata'),
                ('2020-12-25', 'Natale'),
                ('2020-12-26', 'Santo Stefano'),
                
                ('2021-01-01', 'Capodanno'),
                ('2021-01-06', 'Epifania'),
                ('2021-04-04', 'Pasqua'),
                ('2021-04-05', 'Pasquetta'),
                ('2021-04-25', 'Liberazione'),
                ('2021-05-01', 'Lavoro'),
                ('2021-06-02', 'Repubblica'),
                ('2021-08-15', 'Ferragosto'),
                ('2021-11-01', 'Ognissanti'),
                ('2021-12-08', 'Immacolata'),
                ('2021-12-25', 'Natale'),
                ('2021-12-26', 'Santo Stefano'),
                
                ('2022-01-01', 'Capodanno'),
                ('2022-01-06', 'Epifania'),
                ('2022-04-17', 'Pasqua'),
                ('2022-04-18', 'Pasquetta'),
                ('2022-04-25', 'Liberazione'),
                ('2022-05-01', 'Lavoro'),
                ('2022-06-02', 'Repubblica'),
                ('2022-08-15', 'Ferragosto'),
                ('2022-11-01', 'Ognissanti'),
                ('2022-12-08', 'Immacolata'),
                ('2022-12-25', 'Natale'),
                ('2022-12-26', 'Santo Stefano'),
                
                ('2023-01-01', 'Capodanno'),
                ('2023-01-06', 'Epifania'),
                ('2023-04-09', 'Pasqua'),
                ('2023-04-10', 'Pasquetta'),
                ('2023-04-25', 'Liberazione'),
                ('2023-05-01', 'Lavoro'),
                ('2023-06-02', 'Repubblica'),
                ('2023-08-15', 'Ferragosto'),
                ('2023-11-01', 'Ognissanti'),
                ('2023-12-08', 'Immacolata'),
                ('2023-12-25', 'Natale'),
                ('2023-12-26', 'Santo Stefano'),
                
                ('2024-01-01', 'Capodanno'),
                ('2024-01-06', 'Epifania'),
                ('2024-03-31', 'Pasqua'),
                ('2024-04-01', 'Pasquetta'),
                ('2024-04-25', 'Liberazione'),
                ('2024-05-01', 'Lavoro'),
                ('2024-06-02', 'Repubblica'),
                ('2024-08-15', 'Ferragosto'),
                ('2024-11-01', 'Ognissanti'),
                ('2024-12-08', 'Immacolata'),
                ('2024-12-25', 'Natale'),
                ('2024-12-26', 'Santo Stefano'),
                
                ('2025-01-01', 'Capodanno'),
                ('2025-01-06', 'Epifania'),
                ('2025-04-20', 'Pasqua'),
                ('2025-04-21', 'Pasquetta'),
                ('2025-04-25', 'Liberazione'),
                ('2025-05-01', 'Lavoro'),
                ('2025-06-02', 'Repubblica'),
                ('2025-08-15', 'Ferragosto'),
                ('2025-11-01', 'Ognissanti'),
                ('2025-12-08', 'Immacolata'),
                ('2025-12-25', 'Natale'),
                ('2025-12-26', 'Santo Stefano'),
                
                # Festivi 2026 (P0.1)
                ('2026-01-01', 'Capodanno'),
                ('2026-01-06', 'Epifania'),
                ('2026-04-05', 'Pasqua'),
                ('2026-04-06', 'Pasquetta'),
                ('2026-04-25', 'Liberazione'),
                ('2026-05-01', 'Lavoro'),
                ('2026-06-02', 'Repubblica'),
                ('2026-08-15', 'Ferragosto'),
                ('2026-11-01', 'Ognissanti'),
                ('2026-12-08', 'Immacolata'),
                ('2026-12-25', 'Natale'),
                ('2026-12-26', 'Santo Stefano'),
            ]
            
            # Aggiorna festivi
            for holiday_date, description in italian_holidays:
                conn.execute("""
                UPDATE trading_calendar 
                SET is_open = FALSE 
                WHERE venue = ? AND date = ?
                """, [venue, holiday_date])
            
            print(f" Calendario base generato con {len(italian_holidays)} festivi italiani")
        
        # Verifica caricamento
        count_query = "SELECT COUNT(*) FROM trading_calendar WHERE venue = ?"
        total_days = conn.execute(count_query, [venue]).fetchone()[0]
        open_days = conn.execute(f"{count_query} AND is_open = TRUE", [venue]).fetchone()[0]
        
        print(f" Statistiche {venue}: {total_days} giorni totali, {open_days} giorni di trading")
        
        # Verifica anni coperti
        years_query = f"SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM trading_calendar WHERE venue = ? ORDER BY year"
        years = [row[0] for row in conn.execute(years_query, [venue]).fetchall()]
        print(f" Anni coperti: {years}")
        
        conn.commit()
        print(" Trading calendar caricato con successo!")
        return True
        
    except Exception as e:
        print(f" Errore caricamento calendar: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Load Trading Calendar')
    parser.add_argument('--venue', default='BIT', help='Venue code (default: BIT)')
    parser.add_argument('--csv', help='CSV file path (optional)')
    
    args = parser.parse_args()
    
    success = load_trading_calendar(args.venue, args.csv)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
