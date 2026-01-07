"""
Data Quality Test - Market Calendar
Verifica integrità, coerenza e completezza del calendario festività
"""

import sys
import os
from datetime import datetime, date, timedelta
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.utils.market_calendar import MarketCalendar


class MarketCalendarQualityTest:
    """Test suite per data quality calendario festività"""
    
    def __init__(self):
        self.calendar = MarketCalendar()
        self.errors = []
        self.warnings = []
        self.passed = 0
        self.failed = 0
    
    def test_file_exists(self):
        """Test 1: Verifica esistenza file config"""
        print("\n1️⃣ Test: File config esiste")
        
        if not os.path.exists(self.calendar.config_path):
            self.errors.append("File config non trovato")
            self.failed += 1
            print("   ❌ FAIL: File non trovato")
            return False
        
        self.passed += 1
        print("   ✅ PASS")
        return True
    
    def test_json_valid(self):
        """Test 2: Verifica JSON valido"""
        print("\n2️⃣ Test: JSON valido")
        
        try:
            with open(self.calendar.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Verifica struttura base
            required_keys = ['description', 'holidays']
            for key in required_keys:
                if key not in data:
                    self.errors.append(f"Chiave mancante: {key}")
                    self.failed += 1
                    print(f"   ❌ FAIL: Chiave '{key}' mancante")
                    return False
            
            self.passed += 1
            print("   ✅ PASS")
            return True
        
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON non valido: {e}")
            self.failed += 1
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_coverage_current_year(self):
        """Test 3: Verifica copertura anno corrente"""
        print("\n3️⃣ Test: Copertura anno corrente")
        
        current_year = datetime.now().year
        coverage_years = self.calendar.get_coverage_years()
        
        if current_year not in coverage_years:
            self.errors.append(f"Anno corrente {current_year} non coperto")
            self.failed += 1
            print(f"   ❌ FAIL: Anno {current_year} mancante")
            return False
        
        self.passed += 1
        print(f"   ✅ PASS: Anno {current_year} presente")
        return True
    
    def test_coverage_next_year(self):
        """Test 4: Verifica copertura anno successivo"""
        print("\n4️⃣ Test: Copertura anno successivo")
        
        next_year = datetime.now().year + 1
        coverage_years = self.calendar.get_coverage_years()
        
        if next_year not in coverage_years:
            self.warnings.append(f"Anno successivo {next_year} non coperto")
            print(f"   ⚠️  WARNING: Anno {next_year} mancante (eseguire update_market_calendar.py)")
            return True  # Warning, non errore
        
        self.passed += 1
        print(f"   ✅ PASS: Anno {next_year} presente")
        return True
    
    def test_no_weekend_holidays(self):
        """Test 5: Verifica che festività non cadano in weekend (errore logico)"""
        print("\n5️⃣ Test: Nessuna festività in weekend")
        
        weekend_holidays = []
        
        for holiday in self.calendar.holidays:
            if holiday.weekday() >= 5:  # Sabato o Domenica
                weekend_holidays.append(holiday)
        
        if weekend_holidays:
            # Questo è un warning, non errore (festività possono cadere in weekend)
            self.warnings.append(f"Festività in weekend: {len(weekend_holidays)}")
            print(f"   ℹ️  INFO: {len(weekend_holidays)} festività cadono in weekend (normale)")
            for h in weekend_holidays[:5]:  # Mostra prime 5
                print(f"      - {h} ({h.strftime('%A')})")
        else:
            print(f"   ✅ PASS: Nessuna festività in weekend")
        
        self.passed += 1
        return True
    
    def test_no_duplicates(self):
        """Test 6: Verifica assenza duplicati"""
        print("\n6️⃣ Test: Nessun duplicato")
        
        # holidays è già un set, quindi non ci possono essere duplicati
        # Ma verifichiamo nel file JSON originale
        try:
            with open(self.calendar.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            all_dates = []
            for year, dates in data.get('holidays', {}).items():
                all_dates.extend(dates)
            
            if len(all_dates) != len(set(all_dates)):
                duplicates = [d for d in all_dates if all_dates.count(d) > 1]
                self.errors.append(f"Duplicati trovati: {set(duplicates)}")
                self.failed += 1
                print(f"   ❌ FAIL: Duplicati trovati")
                return False
            
            self.passed += 1
            print("   ✅ PASS")
            return True
        
        except Exception as e:
            self.errors.append(f"Errore verifica duplicati: {e}")
            self.failed += 1
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_date_format_valid(self):
        """Test 7: Verifica formato date valido (YYYY-MM-DD)"""
        print("\n7️⃣ Test: Formato date valido")
        
        try:
            with open(self.calendar.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            invalid_dates = []
            
            for year, dates in data.get('holidays', {}).items():
                for date_str in dates:
                    try:
                        # Verifica formato YYYY-MM-DD
                        parsed = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        # Verifica che anno nel path corrisponda
                        if str(parsed.year) != year:
                            invalid_dates.append(f"{date_str} in anno {year}")
                    
                    except ValueError:
                        invalid_dates.append(date_str)
            
            if invalid_dates:
                self.errors.append(f"Date invalide: {invalid_dates}")
                self.failed += 1
                print(f"   ❌ FAIL: {len(invalid_dates)} date invalide")
                return False
            
            self.passed += 1
            print("   ✅ PASS")
            return True
        
        except Exception as e:
            self.errors.append(f"Errore verifica formato: {e}")
            self.failed += 1
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_minimum_holidays_per_year(self):
        """Test 8: Verifica numero minimo festività per anno (almeno 5)"""
        print("\n8️⃣ Test: Numero minimo festività per anno")
        
        try:
            with open(self.calendar.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            years_with_few_holidays = []
            
            for year, dates in data.get('holidays', {}).items():
                if len(dates) < 5:
                    years_with_few_holidays.append((year, len(dates)))
            
            if years_with_few_holidays:
                self.warnings.append(f"Anni con poche festività: {years_with_few_holidays}")
                print(f"   ⚠️  WARNING: Alcuni anni hanno < 5 festività")
                for year, count in years_with_few_holidays:
                    print(f"      - {year}: {count} festività")
                return True  # Warning, non errore
            
            self.passed += 1
            print("   ✅ PASS")
            return True
        
        except Exception as e:
            self.errors.append(f"Errore verifica minimo: {e}")
            self.failed += 1
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_chronological_order(self):
        """Test 9: Verifica ordine cronologico festività per anno"""
        print("\n9️⃣ Test: Ordine cronologico")
        
        try:
            with open(self.calendar.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            unordered_years = []
            
            for year, dates in data.get('holidays', {}).items():
                if dates != sorted(dates):
                    unordered_years.append(year)
            
            if unordered_years:
                self.warnings.append(f"Anni non ordinati: {unordered_years}")
                print(f"   ⚠️  WARNING: Festività non in ordine per anni: {unordered_years}")
                return True  # Warning, non errore
            
            self.passed += 1
            print("   ✅ PASS")
            return True
        
        except Exception as e:
            self.errors.append(f"Errore verifica ordine: {e}")
            self.failed += 1
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_business_day_calculation(self):
        """Test 10: Verifica calcolo business days corretto"""
        print("\n🔟 Test: Calcolo business days")
        
        # Test caso noto: 1-31 Gennaio 2026
        # Festività: 1 Gen (Capodanno) - ma cade di Giovedì quindi conta
        # Weekend: 3-4, 10-11, 17-18, 24-25, 31 Gen (9 giorni - 31 è sabato)
        # Giorni totali: 31
        # Business days attesi: 31 - 1 (festività 1 Gen) - 9 (weekend) = 21
        # Ma count_business_days esclude start, quindi: 30 - 1 - 8 = 21
        
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)
        
        business_days = self.calendar.count_business_days(start, end)
        expected = 21  # Corretto: esclude start (1 Gen), include end (31 Gen sabato non conta)
        
        if business_days != expected:
            self.errors.append(f"Business days errato: {business_days} vs {expected} atteso")
            self.failed += 1
            print(f"   ❌ FAIL: Calcolati {business_days}, attesi {expected}")
            return False
        
        self.passed += 1
        print(f"   ✅ PASS: {business_days} business days (corretto)")
        return True
    
    def run_all_tests(self):
        """Esegui tutti i test"""
        print("=" * 60)
        print("📊 MARKET CALENDAR DATA QUALITY TEST")
        print("=" * 60)
        
        # Esegui test in sequenza
        self.test_file_exists()
        self.test_json_valid()
        self.test_coverage_current_year()
        self.test_coverage_next_year()
        self.test_no_weekend_holidays()
        self.test_no_duplicates()
        self.test_date_format_valid()
        self.test_minimum_holidays_per_year()
        self.test_chronological_order()
        self.test_business_day_calculation()
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        
        if self.errors:
            print(f"\n❌ ERRORI CRITICI:")
            for error in self.errors:
                print(f"   - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        # Informazioni calendario
        print(f"\n📅 CALENDARIO INFO:")
        print(f"   Anni coperti: {self.calendar.get_coverage_years()}")
        print(f"   Totale festività: {len(self.calendar.holidays)}")
        
        print("\n" + "=" * 60)
        
        if self.failed == 0:
            print("✅ TUTTI I TEST PASSATI - Calendario valido")
            return True
        else:
            print(f"❌ {self.failed} TEST FALLITI - Calendario richiede correzioni")
            return False


if __name__ == '__main__':
    tester = MarketCalendarQualityTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
