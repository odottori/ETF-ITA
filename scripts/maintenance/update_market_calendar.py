"""
Auto-update Market Calendar
Aggiunge automaticamente festività per anno successivo se mancante
"""

import sys
import os
from datetime import datetime, date
from dateutil.easter import easter

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.market_calendar import MarketCalendar


def calculate_holidays_for_year(year: int) -> list:
    """
    Calcola festività Borsa Italiana per un anno specifico
    
    Festività fisse:
    - 1 Gennaio: Capodanno
    - 25 Aprile: Festa della Liberazione (solo se giorno lavorativo)
    - 1 Maggio: Festa del Lavoro
    - 25 Dicembre: Natale
    - 26 Dicembre: Santo Stefano
    
    Festività mobili:
    - Venerdì Santo (Good Friday)
    - Lunedì dell'Angelo (Easter Monday)
    """
    
    holidays = []
    
    # Festività fisse
    holidays.append(f"{year}-01-01")  # Capodanno
    
    # 25 Aprile solo se giorno lavorativo (non weekend)
    apr_25 = date(year, 4, 25)
    if apr_25.weekday() < 5:  # Lunedì-Venerdì
        holidays.append(f"{year}-04-25")
    
    holidays.append(f"{year}-05-01")  # Festa del Lavoro
    holidays.append(f"{year}-12-25")  # Natale
    holidays.append(f"{year}-12-26")  # Santo Stefano
    
    # Festività mobili basate su Pasqua
    easter_date = easter(year)
    
    # Venerdì Santo (2 giorni prima di Pasqua)
    from datetime import timedelta
    good_friday = easter_date - timedelta(days=2)
    holidays.append(good_friday.strftime('%Y-%m-%d'))
    
    # Lunedì dell'Angelo (1 giorno dopo Pasqua)
    easter_monday = easter_date + timedelta(days=1)
    holidays.append(easter_monday.strftime('%Y-%m-%d'))
    
    return sorted(holidays)


def update_calendar():
    """Aggiorna calendario con anni mancanti"""
    
    print("🔄 Market Calendar Auto-Update")
    print("=" * 60)
    
    calendar = MarketCalendar()
    
    current_year = datetime.now().year
    next_year = current_year + 1
    
    coverage_years = calendar.get_coverage_years()
    print(f"Anni attualmente coperti: {coverage_years}")
    
    years_to_add = []
    
    # Verifica anno corrente
    if current_year not in coverage_years:
        years_to_add.append(current_year)
        print(f"⚠️  Manca anno corrente: {current_year}")
    
    # Verifica anno successivo
    if next_year not in coverage_years:
        years_to_add.append(next_year)
        print(f"⚠️  Manca anno successivo: {next_year}")
    
    if not years_to_add:
        print(f"✅ Calendario aggiornato (copre {current_year} e {next_year})")
        return True
    
    # Aggiungi anni mancanti
    for year in years_to_add:
        print(f"\n📅 Calcolo festività per anno {year}...")
        holidays = calculate_holidays_for_year(year)
        
        print(f"   Festività calcolate:")
        for holiday in holidays:
            holiday_date = datetime.strptime(holiday, '%Y-%m-%d').date()
            day_name = holiday_date.strftime('%A')
            print(f"   - {holiday} ({day_name})")
        
        success = calendar.add_year_holidays(year, holidays)
        
        if not success:
            print(f"❌ Errore aggiornamento anno {year}")
            return False
    
    print(f"\n✅ Calendario aggiornato con successo")
    print(f"   Nuova copertura: {calendar.get_coverage_years()}")
    
    return True


if __name__ == '__main__':
    success = update_calendar()
    sys.exit(0 if success else 1)
