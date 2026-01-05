#!/usr/bin/env python3
"""
Fix All Issues - ETF Italia Project v10
Versione ottimizzata e pulita per risoluzione integrity issues
"""

import sys
import os
import duckdb
import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DataGapFixer:
    """Classe per il fix dei gap nei dati di mercato"""
    
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn
        self.fixed_count = 0
        self.error_count = 0
    
    def fetch_yahoo_finance_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[Dict]:
        """Ottieni dati da Yahoo Finance con gestione errori"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date)
            
            if not data.empty:
                return data
            return None
            
        except Exception as e:
            print(f"   ️ Yahoo Finance error per {symbol}: {e}")
            return None
    
    def fetch_stooq_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[List[Tuple]]:
        """Ottieni dati da Stooq con gestione errori"""
        try:
            stooq_symbol = self._convert_to_stooq_symbol(symbol)
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&d1={start_str}&d2={end_str}&i=d"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = []
                lines = response.text.strip().split('\n')
                
                for line in lines[1:]:  # Skip header
                    parts = line.split(',')
                    if len(parts) >= 5:
                        date_str = parts[0]
                        close_price = float(parts[4])
                        volume = int(parts[5]) if len(parts) > 5 else 0
                        
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        data.append((date_obj, close_price, volume))
                
                return data
            
        except Exception as e:
            print(f"   ️ Stooq error per {symbol}: {e}")
            return None
    
    def _convert_to_stooq_symbol(self, symbol: str) -> str:
        """Converte simbolo per Stooq"""
        mapping = {
            'CSSPX.MI': 'csspx',
            'XS2L.MI': 'xs2l',
            '^GSPC': 'spx'
        }
        return mapping.get(symbol, symbol.lower().replace('.mi', ''))
    
    def forward_fill_data(self, symbol: str, missing_dates: List[datetime]) -> int:
        """Fill forward con ultimo prezzo disponibile"""
        try:
            last_data = self.conn.execute("""
            SELECT adj_close, volume
            FROM market_data
            WHERE symbol = ? AND date < ?
            ORDER BY date DESC
            LIMIT 1
            """, [symbol, missing_dates[0]]).fetchone()
            
            if not last_data:
                return 0
            
            last_price, last_volume = last_data
            
            for missing_date in missing_dates:
                self.conn.execute("""
                INSERT INTO market_data 
                (symbol, date, high, low, close, adj_close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    symbol, missing_date,
                    last_price, last_price, last_price,
                    last_price, last_volume
                ])
            
            return len(missing_dates)
            
        except Exception as e:
            print(f"    Forward fill error per {symbol}: {e}")
            return 0
    
    def insert_data_from_dataframe(self, symbol: str, data: Dict, missing_dates: List[datetime]) -> int:
        """Inserisci dati da DataFrame di Yahoo Finance"""
        inserted = 0
        for missing_date in missing_dates:
            if missing_date in data.index:
                row = data.loc[missing_date]
                
                self.conn.execute("""
                INSERT OR REPLACE INTO market_data 
                (symbol, date, high, low, close, adj_close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    symbol, missing_date,
                    row['High'], row['Low'], row['Close'], 
                    row['Adj Close'], row['Volume']
                ])
                inserted += 1
        
        return inserted
    
    def insert_data_from_list(self, symbol: str, data: List[Tuple], missing_dates: List[datetime]) -> int:
        """Inserisci dati da lista Stooq"""
        inserted = 0
        data_dict = {date: (price, volume) for date, price, volume in data}
        
        for missing_date in missing_dates:
            if missing_date in data_dict:
                price, volume = data_dict[missing_date]
                
                self.conn.execute("""
                INSERT OR REPLACE INTO market_data 
                (symbol, date, high, low, close, adj_close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    symbol, missing_date,
                    price, price, price, price, volume
                ])
                inserted += 1
        
        return inserted
    
    def fix_gap_for_symbol(self, symbol: str, gaps: List[Tuple]) -> int:
        """Fix gaps per un singolo simbolo"""
        if not gaps:
            return 0
        
        print(f"\n Fix gaps per {symbol} ({len(gaps)} gaps)...")
        
        # Mostra i gap più grandi
        print(f"    Gap più grandi:")
        for gap in gaps[:3]:
            _, date, prev_date, gap_days = gap
            print(f"      {prev_date} → {date} ({gap_days} giorni)")
        
        fixed_count = 0
        
        for gap in gaps:
            symbol_name, date, prev_date, gap_days = gap
            
            # Genera date mancanti
            missing_dates = self._get_missing_trading_dates(symbol, prev_date, date)
            
            if not missing_dates:
                continue
            
            # Prova Yahoo Finance
            yf_data = self.fetch_yahoo_finance_data(symbol, missing_dates[0], missing_dates[-1] + timedelta(days=1))
            if yf_data is not None:
                inserted = self.insert_data_from_dataframe(symbol, yf_data, missing_dates)
                fixed_count += inserted
                print(f"    {inserted} giorni da Yahoo Finance")
                continue
            
            # Fallback Stooq
            stooq_data = self.fetch_stooq_data(symbol, missing_dates[0], missing_dates[-1] + timedelta(days=1))
            if stooq_data:
                inserted = self.insert_data_from_list(symbol, stooq_data, missing_dates)
                fixed_count += inserted
                print(f"    {inserted} giorni da Stooq")
                continue
            
            # Fallback forward fill
            inserted = self.forward_fill_data(symbol, missing_dates)
            fixed_count += inserted
            print(f"    {inserted} giorni con forward fill")
        
        print(f"    {symbol}: {fixed_count} giorni fissati")
        return fixed_count
    
    def _get_missing_trading_dates(self, symbol: str, prev_date: datetime, current_date: datetime) -> List[datetime]:
        """Ottieni date mancanti che sono giorni di trading"""
        missing_dates = []
        date_cursor = prev_date + timedelta(days=1)
        
        while date_cursor < current_date:
            # Verifica se è giorno di trading
            trading_check = self.conn.execute("""
            SELECT is_open FROM trading_calendar 
            WHERE date = ? AND venue = 'BIT'
            """, [date_cursor]).fetchone()
            
            if trading_check and trading_check[0]:
                missing_dates.append(date_cursor)
            
            date_cursor += timedelta(days=1)
        
        return missing_dates


class IssueAnalyzer:
    """Classe per analizzare gli integrity issues"""
    
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn
    
    def get_all_gaps(self) -> List[Tuple]:
        """Ottieni tutti i gap >5 giorni"""
        query = """
        WITH gaps AS (
            SELECT 
                symbol,
                date,
                LAG(date) OVER (PARTITION BY symbol ORDER BY date) as prev_date,
                (date - LAG(date) OVER (PARTITION BY symbol ORDER BY date)) as gap_days
            FROM market_data
            WHERE symbol IN ('CSSPX.MI', 'XS2L.MI')
        )
        SELECT symbol, date, prev_date, gap_days
        FROM gaps
        WHERE prev_date IS NOT NULL AND gap_days > 5
        ORDER BY symbol, gap_days DESC
        """
        return self.conn.execute(query).fetchall()
    
    def get_zombie_count(self) -> int:
        """Conteggio zombie prices"""
        query = """
        SELECT COUNT(*) as zombie_count
        FROM market_data md
        JOIN trading_calendar tc ON md.date = tc.date
        WHERE tc.venue = 'BIT' AND tc.is_open = TRUE
        AND md.volume = 0 AND md.adj_close > 0
        """
        return self.conn.execute(query).fetchone()[0]
    
    def get_data_stats(self) -> Tuple:
        """Statistiche dati"""
        query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as symbols,
            COUNT(DISTINCT date) as dates,
            MIN(date) as min_date,
            MAX(date) as max_date
        FROM market_data
        """
        return self.conn.execute(query).fetchone()


def fix_all_issues():
    """Funzione principale per risolvere tutti gli integrity issues"""
    
    print(" FIX ALL ISSUES - ETF Italia Project v10 (Versione Ottimizzata)")
    print("=" * 60)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'etf_data.duckdb')
    
    try:
        conn = duckdb.connect(db_path)
        
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        print(" Analisi dettagliata dei 75 issues...")
        
        # Analisi iniziale
        analyzer = IssueAnalyzer(conn)
        all_gaps = analyzer.get_all_gaps()
        zombie_count = analyzer.get_zombie_count()
        
        print(f" Gaps totali da risolvere: {len(all_gaps)}")
        print(f" Zombie prices: {zombie_count}")
        
        # Fix gaps
        gap_fixer = DataGapFixer(conn)
        total_fixed = 0
        
        for symbol in ['CSSPX.MI', 'XS2L.MI']:
            symbol_gaps = [gap for gap in all_gaps if gap[0] == symbol]
            fixed = gap_fixer.fix_gap_for_symbol(symbol, symbol_gaps)
            total_fixed += fixed
        
        # Verifica finale
        print(f"\n Verifica finale...")
        
        remaining_gaps = analyzer.get_all_gaps()
        remaining_zombies = analyzer.get_zombie_count()
        total_issues = len(remaining_gaps) + remaining_zombies
        
        # Statistiche finali
        stats = analyzer.get_data_stats()
        total_records, symbols, dates, min_date, max_date = stats
        
        print(f" RISULTATI FINALI:")
        print(f"    Zombie prices: {remaining_zombies}")
        print(f"    Large gaps rimanenti: {len(remaining_gaps)}")
        print(f"   ️ Total issues: {total_issues}")
        print(f"    Giorni fissati: {total_fixed}")
        
        print(f"\n STATISTICHE DATI AGGIORNATI:")
        print(f"   Records totali: {total_records:,}")
        print(f"   Simboli: {symbols}")
        print(f"   Date uniche: {dates:,}")
        print(f"   Periodo: {min_date} → {max_date}")
        
        # Decisione finale
        print(f"\n VALUTAZIONE FINALE:")
        
        if total_issues == 0:
            print(f"    TUTTI GLI ISSUES RISOLTI!")
            print(f"   • Sistema perfetto: 0 issues")
            print(f"   • Pronto per produzione senza warning")
        elif total_issues <= 10:
            print(f"    ISSUES MINIMI RISOLTI!")
            print(f"   • Issues residui: {total_issues} (accettabili)")
            print(f"   • Sistema quasi perfetto")
        elif total_issues <= 30:
            print(f"    ISSUES PARZIALMENTE RISOLTI")
            print(f"   • Issues residui: {total_issues} (gestibili)")
            print(f"   • Sistema migliorato")
        else:
            print(f"   ️ ISSUES ANCORA DA RISOLVERE")
            print(f"   • Issues residui: {total_issues}")
            print(f"   • Azioni aggiuntive necessarie")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f" Errore fix all issues: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    success = fix_all_issues()
    sys.exit(0 if success else 1)
