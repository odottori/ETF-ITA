"""
Market Calendar Utility
Gestisce calendario festività per Borsa Italiana/mercati europei
"""

import json
import os
from datetime import datetime, date, timedelta
from typing import Set, List, Optional


class MarketCalendar:
    """Gestisce calendario festività mercati"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(base_dir, 'config', 'market_holidays.json')
        
        self.config_path = config_path
        self.holidays: Set[date] = set()
        self._load_holidays()
    
    def _load_holidays(self):
        """Carica festività da config file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Converti stringhe date in date objects (festività pianificate)
            for year, dates in data.get('holidays', {}).items():
                for date_str in dates:
                    holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    self.holidays.add(holiday_date)
            
            # Aggiungi chiusure eccezionali (terremoti, emergenze, ecc.)
            exceptional = data.get('exceptional_closures', {}).get('dates', [])
            for date_str in exceptional:
                closure_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                self.holidays.add(closure_date)
            
            regular_count = len(self.holidays) - len(exceptional)
            
            if exceptional:
                print(f"✅ Caricati {regular_count} giorni festivi + {len(exceptional)} chiusure eccezionali")
            else:
                print(f"✅ Caricati {len(self.holidays)} giorni festivi da {self.config_path}")
        
        except FileNotFoundError:
            print(f"⚠️  File festività non trovato: {self.config_path}")
            print(f"   Il sistema userà solo weekend per calcolo business days")
        except Exception as e:
            print(f"⚠️  Errore caricamento festività: {e}")
            print(f"   Il sistema userà solo weekend per calcolo business days")
    
    def is_holiday(self, check_date: date) -> bool:
        """Verifica se una data è festività"""
        return check_date in self.holidays
    
    def is_business_day(self, check_date: date) -> bool:
        """Verifica se una data è giorno lavorativo (non weekend, non festività)"""
        # Weekend: sabato (5) e domenica (6)
        if check_date.weekday() >= 5:
            return False
        
        # Festività
        if self.is_holiday(check_date):
            return False
        
        return True
    
    def count_business_days(self, start_date: date, end_date: date) -> int:
        """Conta giorni lavorativi tra due date (escluso start, incluso end)"""
        count = 0
        current = start_date + timedelta(days=1)
        
        while current <= end_date:
            if self.is_business_day(current):
                count += 1
            current += timedelta(days=1)
        
        return count
    
    def get_next_business_day(self, from_date: date) -> date:
        """Ottieni prossimo giorno lavorativo"""
        current = from_date + timedelta(days=1)
        
        while not self.is_business_day(current):
            current += timedelta(days=1)
        
        return current
    
    def get_holidays_in_range(self, start_date: date, end_date: date) -> List[date]:
        """Ottieni lista festività in un range"""
        holidays_in_range = []
        
        for holiday in sorted(self.holidays):
            if start_date <= holiday <= end_date:
                holidays_in_range.append(holiday)
        
        return holidays_in_range
    
    def needs_update(self) -> bool:
        """Verifica se calendario necessita aggiornamento (manca anno corrente o successivo)"""
        current_year = datetime.now().year
        next_year = current_year + 1
        
        # Verifica se abbiamo festività per anno corrente e successivo
        has_current_year = any(h.year == current_year for h in self.holidays)
        has_next_year = any(h.year == next_year for h in self.holidays)
        
        return not (has_current_year and has_next_year)
    
    def get_coverage_years(self) -> List[int]:
        """Ottieni lista anni coperti dal calendario"""
        years = set(h.year for h in self.holidays)
        return sorted(years)
    
    def add_year_holidays(self, year: int, holidays: List[str]):
        """Aggiungi festività per un anno (per auto-update)"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Aggiungi nuovo anno
            data['holidays'][str(year)] = holidays
            data['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            
            # Salva
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Ricarica
            self._load_holidays()
            
            print(f"✅ Aggiunte festività per anno {year}")
            return True
        
        except Exception as e:
            print(f"❌ Errore aggiornamento calendario: {e}")
            return False
    
    def add_exceptional_closure(self, closure_date: date, reason: str = ""):
        """
        Aggiungi chiusura eccezionale (terremoto, emergenza, ecc.)
        
        Args:
            closure_date: Data chiusura eccezionale
            reason: Motivo chiusura (opzionale)
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Inizializza exceptional_closures se non esiste
            if 'exceptional_closures' not in data:
                data['exceptional_closures'] = {
                    'description': 'Chiusure eccezionali non pianificate',
                    'dates': []
                }
            
            date_str = closure_date.strftime('%Y-%m-%d')
            
            # Verifica se già presente
            if date_str in data['exceptional_closures']['dates']:
                print(f"ℹ️  Chiusura eccezionale {date_str} già registrata")
                return True
            
            # Aggiungi
            data['exceptional_closures']['dates'].append(date_str)
            data['exceptional_closures']['dates'].sort()
            data['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            
            # Aggiungi nota se fornita
            if reason:
                if 'reasons' not in data['exceptional_closures']:
                    data['exceptional_closures']['reasons'] = {}
                data['exceptional_closures']['reasons'][date_str] = reason
            
            # Salva
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Ricarica
            self._load_holidays()
            
            reason_text = f" ({reason})" if reason else ""
            print(f"✅ Registrata chiusura eccezionale: {date_str}{reason_text}")
            return True
        
        except Exception as e:
            print(f"❌ Errore registrazione chiusura eccezionale: {e}")
            return False


# Singleton instance
_calendar_instance: Optional[MarketCalendar] = None


def get_market_calendar() -> MarketCalendar:
    """Ottieni istanza singleton del calendario"""
    global _calendar_instance
    
    if _calendar_instance is None:
        _calendar_instance = MarketCalendar()
    
    return _calendar_instance


# Convenience functions
def is_business_day(check_date: date) -> bool:
    """Verifica se una data è giorno lavorativo"""
    return get_market_calendar().is_business_day(check_date)


def count_business_days(start_date: date, end_date: date) -> int:
    """Conta giorni lavorativi tra due date"""
    return get_market_calendar().count_business_days(start_date, end_date)


def get_next_business_day(from_date: date) -> date:
    """Ottieni prossimo giorno lavorativo"""
    return get_market_calendar().get_next_business_day(from_date)


if __name__ == '__main__':
    # Test
    calendar = MarketCalendar()
    
    print(f"\n📅 Market Calendar Test")
    print(f"=" * 60)
    print(f"Anni coperti: {calendar.get_coverage_years()}")
    print(f"Totale festività: {len(calendar.holidays)}")
    
    # Test date
    test_date = date(2026, 1, 1)  # Capodanno
    print(f"\n{test_date} è festività? {calendar.is_holiday(test_date)}")
    print(f"{test_date} è giorno lavorativo? {calendar.is_business_day(test_date)}")
    
    # Test business days
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    business_days = calendar.count_business_days(start, end)
    print(f"\nGiorni lavorativi tra {start} e {end}: {business_days}")
    
    # Festività in range
    holidays = calendar.get_holidays_in_range(start, end)
    print(f"Festività nel periodo: {holidays}")
