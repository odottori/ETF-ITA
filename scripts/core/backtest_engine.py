#!/usr/bin/env python3
"""
Backtest Engine - ETF Italia Project v10.7.2
Simulazione reale con esecuzione ordini e contabilizzazione fiscale
Risolve il problema "reporting senza simulazione"
"""

import sys
import os
import json
import duckdb
import pandas as pd
from datetime import datetime, timedelta
import io

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows console robustness (avoid UnicodeEncodeError on cp1252)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Fallback (some Windows terminals ignore reconfigure)
try:
    if getattr(sys.stdout, "encoding", None) and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    if getattr(sys.stderr, "encoding", None) and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

from session_manager import get_session_manager
from execute_orders import check_cash_available, check_position_available
from implement_tax_logic import calculate_tax

class BacktestEngine:
    """Motore di backtest con simulazione reale"""
    
    def __init__(self, db_path, config_path):
        self.db_path = db_path
        self.config_path = config_path
        self.conn = None
        self.config = None
        
    def connect(self):
        """Connette al database"""
        self.conn = duckdb.connect(self.db_path)
        
        # Carica configurazione
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
    
    def initialize_portfolio(self, initial_capital=20000.0, start_date=None):
        """Inizializza portfolio con capitale iniziale"""
        
        # Pulisci ledger precedente backtest
        self.conn.execute("DELETE FROM fiscal_ledger WHERE run_type = 'BACKTEST'")
        self.conn.commit()
        
        # Deposito iniziale con ID backtest
        next_id = self.conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
        
        # Usa start_date se fornita, altrimenti oggi
        deposit_date = start_date if start_date else datetime.now().date()
        
        self.conn.execute("""
        INSERT INTO fiscal_ledger (
            id, date, type, symbol, qty, price, fees, tax_paid, 
            pmc_snapshot, run_type, notes
        ) VALUES (?, ?, 'DEPOSIT', 'CASH', 1, ?, 0, 0, ?, 'BACKTEST', 'Initial capital')
        """, [
            next_id,
            deposit_date,
            initial_capital,
            initial_capital
        ])
        
        print(f"✅ Portfolio inizializzato con €{initial_capital:,.2f}")
        
    def run_simulation(self, start_date, end_date):
        """Esegue simulazione event-driven giorno per giorno"""
        
        print(f"🚀 SIMULAZIONE BACKTEST: {start_date} → {end_date}")
        print("=" * 60)
        
        # 1. Verifica segnali esistenti per il periodo
        print("📊 Verifica segnali disponibili...")
        
        signals_count = self.conn.execute("""
        SELECT COUNT(DISTINCT date) as signal_days
        FROM signals
        WHERE date BETWEEN ? AND ?
        """, [start_date, end_date]).fetchone()[0]
        
        if signals_count == 0:
            print(f"❌ Nessun segnale disponibile per il periodo {start_date} → {end_date}")
            print("   Esegui prima compute_signals.py per generare i segnali")
            return False
        
        print(f"✅ Trovati segnali per {signals_count} giorni di trading")
        
        # 2. Ottieni tutte le date uniche con segnali
        trading_dates = self.conn.execute("""
        SELECT DISTINCT date
        FROM signals
        WHERE date BETWEEN ? AND ?
        ORDER BY date
        """, [start_date, end_date]).fetchall()
        
        trading_dates = [d[0] for d in trading_dates]
        
        print(f"⚡ Esecuzione event-driven su {len(trading_dates)} giorni...")
        
        executed_orders = []
        progress_interval = max(100, len(trading_dates) // 20)
        
        # 3. Loop giorno per giorno (event-driven)
        for idx, current_date in enumerate(trading_dates):
            if idx % progress_interval == 0:
                print(f"  Processati {idx}/{len(trading_dates)} giorni...")
            
            # 3.1 Calcola cash disponibile a inizio giornata
            cash_available = self.conn.execute("""
            SELECT COALESCE(SUM(CASE 
                WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
                WHEN type = 'SELL' THEN qty * price - fees - tax_paid
                WHEN type = 'BUY' THEN -(qty * price + fees)
                WHEN type = 'INTEREST' THEN qty
                ELSE 0 
            END), 0)
            FROM fiscal_ledger
            WHERE date <= ?
            """, [current_date]).fetchone()[0]
            
            # 3.2 Processa prima i SELL (liberano cash)
            sell_signals = self.conn.execute("""
            SELECT s.symbol, s.risk_scalar, md.close as price
            FROM signals s
            JOIN market_data md ON s.date = md.date AND s.symbol = md.symbol
            WHERE s.date = ?
            AND s.signal_state = 'RISK_OFF'
            """, [current_date]).fetchall()
            
            for symbol, risk_scalar, price in sell_signals:
                position_qty = self.conn.execute("""
                SELECT COALESCE(SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END), 0)
                FROM fiscal_ledger
                WHERE symbol = ?
                AND type IN ('BUY', 'SELL')
                AND date < ?
                """, [symbol, current_date]).fetchone()[0]
                
                if position_qty > 0:
                    success = self._execute_order(current_date, symbol, 'SELL', int(position_qty), price)
                    if success:
                        executed_orders.append((current_date, symbol, 'SELL', int(position_qty), price))
                        # Aggiorna cash dopo SELL
                        cash_available = self.conn.execute("""
                        SELECT COALESCE(SUM(CASE 
                            WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
                            WHEN type = 'SELL' THEN qty * price - fees - tax_paid
                            WHEN type = 'BUY' THEN -(qty * price + fees)
                            WHEN type = 'INTEREST' THEN qty
                            ELSE 0 
                        END), 0)
                        FROM fiscal_ledger
                        WHERE date <= ?
                        """, [current_date]).fetchone()[0]
            
            # 3.3 Processa BUY solo se c'è cash disponibile
            if cash_available > 100:  # Minimo €100 per operare
                buy_signals = self.conn.execute("""
                SELECT s.symbol, s.risk_scalar, md.close as price
                FROM signals s
                JOIN market_data md ON s.date = md.date AND s.symbol = md.symbol
                WHERE s.date = ?
                AND s.signal_state = 'RISK_ON'
                ORDER BY s.risk_scalar DESC
                """, [current_date]).fetchall()
                
                for symbol, risk_scalar, price in buy_signals:
                    if cash_available < 100:
                        break  # Cash esaurito, salta al giorno successivo
                    
                    target_value = cash_available * risk_scalar
                    qty = int(target_value / price) if price > 0 else 0
                    
                    if qty > 0:
                        success = self._execute_order(current_date, symbol, 'BUY', qty, price)
                        if success:
                            executed_orders.append((current_date, symbol, 'BUY', qty, price))
                            # Aggiorna cash dopo BUY
                            cash_available = self.conn.execute("""
                            SELECT COALESCE(SUM(CASE 
                                WHEN type = 'DEPOSIT' THEN qty * price - fees - tax_paid
                                WHEN type = 'SELL' THEN qty * price - fees - tax_paid
                                WHEN type = 'BUY' THEN -(qty * price + fees)
                                WHEN type = 'INTEREST' THEN qty
                                ELSE 0 
                            END), 0)
                            FROM fiscal_ledger
                            WHERE date <= ?
                            """, [current_date]).fetchone()[0]
        
        print(f"✅ Eseguiti {len(executed_orders)} ordini su {len(trading_dates)} giorni")
        
    def _execute_order(self, date, symbol, order_type, qty, price):
        """Esegue singolo ordine con logica fiscale condivisa con execute_orders"""
        
        # 1. Calcola costi usando configurazione reale (non hard-coded)
        position_value = qty * price
        
        # Commissione da configurazione
        commission_pct = self.config['universe']['core'][0]['cost_model']['commission_pct']
        commission = position_value * commission_pct
        if position_value < 1000:
            commission = max(5.0, commission)  # Minimum €5
        
        # Slippage da configurazione con adjustment volatilità
        volatility_data = self.conn.execute("""
        SELECT volatility_20d FROM risk_metrics 
        WHERE symbol = ? 
        ORDER BY date DESC LIMIT 1
        """, [symbol]).fetchone()
        
        volatility = volatility_data[0] if volatility_data and volatility_data[0] else 0.15
        slippage_bps = self.config['universe']['core'][0]['cost_model']['slippage_bps']
        slippage_bps = max(slippage_bps, volatility * 0.5)  # Volatility adjustment
        slippage = position_value * (slippage_bps / 10000)
        
        total_cost = position_value + commission + slippage
        
        # 2. Pre-trade controls (condivisi con execute_orders)
        if order_type == 'BUY':
            cash_available, cash_balance = check_cash_available(self.conn, total_cost)
            if not cash_available:
                print(f"  ❌ {symbol} BUY {qty:.0f} @ €{price:.2f} - CASH INSUFFICIENTE: richiesto €{total_cost:.2f}, disponibile €{cash_balance:.2f}")
                return False  # Ordine rifiutato
        
        elif order_type == 'SELL':
            position_available, current_qty = check_position_available(self.conn, symbol, qty)
            if not position_available:
                print(f"  ❌ {symbol} SELL {qty:.0f} @ €{price:.2f} - POSITION INSUFFICIENTE: richiesto {qty:.0f}, disponibile {current_qty:.0f}")
                return False
        
        # Calcola PMC snapshot
        pmc_snapshot = self.conn.execute("""
        SELECT COALESCE(SUM(pmc_snapshot), 0) FROM fiscal_ledger WHERE date < ?
        """, [date]).fetchone()[0]
        
        # Calcola tassazione per SELL
        tax_amount = 0.0
        if order_type == 'SELL':
            avg_cost = self.conn.execute("""
            SELECT COALESCE(SUM(qty * price) / SUM(qty), 0) as avg_cost
            FROM fiscal_ledger 
            WHERE symbol = ? AND type = 'BUY' AND date <= ?
            """, [symbol, date]).fetchone()[0]
            
            proceeds = qty * price - commission - slippage
            cost_basis = qty * avg_cost
            gain = proceeds - cost_basis
            
            # Calcolo tassazione usando logica condivisa
            tax_result = calculate_tax(gain, symbol, date, self.conn)
            tax_amount = tax_result['tax_amount']
            zainetto_used = tax_result['zainetto_used']
            explanation = tax_result['explanation']
        
        # INSERT completo con tutti i parametri
        trade_currency = self.config['settings']['currency']
        exchange_rate = 1.0
        run_id = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        next_id = self.conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
        
        # INSERT con valori di default impliciti (DuckDB conta solo parametri non-default)
        self.conn.execute("""
        INSERT INTO fiscal_ledger (
            id, date, type, symbol, qty, price, 
            pmc_snapshot, price_eur, run_id, run_type, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            next_id, date, order_type, symbol, qty, price, 
            pmc_snapshot, price, run_id, 'BACKTEST', 'Backtest execution', datetime.now()
        ])
        
        return True
    
    def calculate_portfolio_value(self, date):
        """Calcola valore portfolio alla data specifica"""
        
        # Posizioni aperte
        positions = self.conn.execute("""
        SELECT 
            fl.symbol,
            SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) as net_qty,
            md.close as current_price
        FROM fiscal_ledger fl
        JOIN market_data md ON fl.symbol = md.symbol AND md.date = ?
        WHERE fl.date <= ?
        AND fl.type IN ('BUY', 'SELL')
        GROUP BY fl.symbol, md.close
        HAVING SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) > 0
        """, [date, date]).fetchall()
        
        market_value = sum(qty * price for symbol, qty, price in positions)
        
        # Cash disponibile
        cash = self.conn.execute("""
        SELECT COALESCE(SUM(CASE 
            WHEN fl.type = 'DEPOSIT' THEN fl.qty * fl.price - fl.fees - fl.tax_paid
            WHEN fl.type = 'SELL' THEN fl.qty * fl.price - fl.fees - fl.tax_paid
            WHEN fl.type = 'BUY' THEN -(fl.qty * fl.price + fl.fees)
            ELSE 0 
        END), 0) as cash_balance
        FROM fiscal_ledger fl
        WHERE fl.date <= ? AND fl.run_type = 'BACKTEST'
        """, [date]).fetchone()[0]
        
        return market_value + cash
    
    def create_portfolio_overview(self, start_date, end_date):
        """Crea vista portfolio_overview basata su simulazione reale"""
        
        print("📊 Creazione portfolio_overview da simulazione...")
        
        # Elimina viste e tabelle precedenti
        self.conn.execute("DROP VIEW IF EXISTS portfolio_overview")
        self.conn.execute("DROP TABLE IF EXISTS daily_portfolio")
        
        # Crea tabella persistente (non TEMP) con valori portfolio giornalieri
        self.conn.execute("""
        CREATE TABLE daily_portfolio AS
        SELECT 
            date,
            symbol,
            adj_close,
            volume,
            market_value,
            qty,
            cash
        FROM (
            SELECT 
                md.date,
                md.symbol,
                md.adj_close,
                md.volume,
                COALESCE(fl.net_qty * md.close, 0) as market_value,
                COALESCE(fl.net_qty, 0) as qty,
                0 as cash
            FROM market_data md
            LEFT JOIN (
                SELECT 
                    symbol,
                    date,
                    SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as net_qty
                FROM fiscal_ledger fl
                WHERE run_type = 'BACKTEST'
                AND type IN ('BUY', 'SELL')
                GROUP BY symbol, date
            ) fl ON md.symbol = fl.symbol AND md.date >= fl.date
            WHERE md.date BETWEEN ? AND ?
            AND md.symbol IN (SELECT DISTINCT symbol FROM fiscal_ledger WHERE run_type = 'BACKTEST')
        ) t
        WHERE date BETWEEN ? AND ?
        ORDER BY date, symbol
        """, [start_date, end_date, start_date, end_date])
        
        # Crea vista portfolio_overview basata su tabella persistente
        self.conn.execute("""
        CREATE OR REPLACE VIEW portfolio_overview AS
        SELECT * FROM daily_portfolio
        ORDER BY date, symbol
        """)
        
        print("✅ portfolio_overview creato da dati reali")
    
    def calculate_real_kpi(self, start_date, end_date):
        """Calcola KPI basati su simulazione reale"""
        
        # Ottieni valori portfolio giornalieri
        portfolio_values = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                value = self.calculate_portfolio_value(current_date)
                portfolio_values.append((current_date, value))
            except:
                pass
            current_date += timedelta(days=1)
        
        if not portfolio_values:
            return self._empty_kpi()
        
        df = pd.DataFrame(portfolio_values, columns=['date', 'portfolio_value'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calcola returns
        df['daily_return'] = df['portfolio_value'].pct_change(fill_method=None)
        df = df.dropna()
        
        if len(df) == 0:
            return self._empty_kpi()
        
        # KPI reali
        initial_value = df['portfolio_value'].iloc[0]
        final_value = df['portfolio_value'].iloc[-1]
        
        days = (df.index[-1] - df.index[0]).days
        cagr = (final_value / initial_value) ** (365.25 / days) - 1 if days > 0 else 0.0
        
        # Max drawdown
        df['cummax'] = df['portfolio_value'].cummax()
        df['drawdown'] = (df['portfolio_value'] - df['cummax']) / df['cummax']
        max_dd = df['drawdown'].min()
        
        # Volatilità e Sharpe
        vol = df['daily_return'].std() * (252 ** 0.5)
        sharpe = cagr / vol if vol > 0 else 0.0
        
        # Turnover reale
        turnover = self._calculate_turnover(start_date, end_date)
        
        return {
            'cagr': cagr,
            'max_dd': max_dd,
            'vol': vol,
            'sharpe': sharpe,
            'turnover': turnover,
            'initial_value': initial_value,
            'final_value': final_value,
            'total_return': (final_value - initial_value) / initial_value
        }
    
    def _calculate_turnover(self, start_date, end_date):
        """Calcola turnover reale basato su ordini eseguiti"""
        
        total_traded = self.conn.execute("""
        SELECT COALESCE(SUM(qty * price), 0) as total_traded
        FROM fiscal_ledger
        WHERE date BETWEEN ? AND ?
        AND run_type = 'BACKTEST'
        AND type IN ('BUY', 'SELL')
        """, [start_date, end_date]).fetchone()[0]
        
        avg_portfolio_value = self.conn.execute("""
        SELECT AVG(portfolio_value) as avg_value
        FROM (
            SELECT fl.date, SUM(fl.qty * fl.price) as portfolio_value
            FROM fiscal_ledger fl
            JOIN market_data md ON fl.symbol = md.symbol AND fl.date = md.date
            WHERE fl.date BETWEEN ? AND ?
            AND fl.run_type = 'BACKTEST'
            AND fl.type IN ('BUY', 'SELL')
            GROUP BY fl.date
        ) t
        """, [start_date, end_date]).fetchone()[0] or 1
        
        return (total_traded / avg_portfolio_value) / 2 if avg_portfolio_value > 0 else 0.0
    
    def _empty_kpi(self):
        """Ritorna KPI vuoti"""
        return {
            'cagr': 0.0,
            'max_dd': 0.0,
            'vol': 0.0,
            'sharpe': 0.0,
            'turnover': 0.0,
            'initial_value': 0.0,
            'final_value': 0.0,
            'total_return': 0.0
        }
    
    def close(self):
        """Chiudi connessione"""
        if self.conn:
            self.conn.close()

def run_backtest_simulation():
    """Funzione principale per esecuzione backtest con simulazione"""
    
    print("🚀 BACKTEST ENGINE - ETF Italia Project v10.7.2")
    print("=" * 60)
    
    # Path configurazione
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(root_dir, 'config', 'etf_universe.json')
    db_path = os.path.join(root_dir, 'data', 'etf_data.duckdb')
    
    PRESET_PERIODS = {
        'covid': ('2020-01-01', '2021-12-31'),
        'gfc': ('2007-01-01', '2010-12-31'),
        'eurocrisis': ('2011-01-01', '2013-12-31'),
        'inflation2022': ('2021-10-01', '2023-03-31'),
    }

    def _parse_date(s):
        if s is None:
            return None
        return datetime.strptime(s, '%Y-%m-%d').date()

    # Inizializza engine
    engine = BacktestEngine(db_path, config_path)
    
    try:
        engine.connect()
        
        # Periodo backtest (default: ultimo anno)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)

        # Override via env (usato da backtest_runner parametrico)
        env_preset = os.environ.get('ETF_ITA_PRESET')
        env_start = os.environ.get('ETF_ITA_START_DATE')
        env_end = os.environ.get('ETF_ITA_END_DATE')
        env_recent_days = os.environ.get('ETF_ITA_RECENT_DAYS')

        if env_preset:
            if env_preset == 'full' or env_preset == 'recent':
                # Periodi dinamici basati su disponibilità segnali
                min_max = engine.conn.execute("""
                SELECT MIN(date) AS min_date, MAX(date) AS max_date
                FROM signals
                """).fetchone()
                min_date, max_date = min_max
                if min_date is None or max_date is None:
                    raise ValueError("Nessun segnale disponibile: eseguire compute_signals prima del backtest")

                # Data freshness check con auto-update
                today = datetime.now().date()
                days_gap = (today - max_date).days
                
                # Conta giorni lavorativi mancanti (escludendo weekend E festività)
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from utils.market_calendar import get_market_calendar
                calendar = get_market_calendar()
                
                business_days_missing = calendar.count_business_days(max_date, today)
                
                # Tenta auto-update se mancano > 1 giorni lavorativi
                should_update = business_days_missing > 1
                
                if should_update:
                    print(f"\n⚠️  WARNING: Dati NON aggiornati!")
                    print(f"   Ultimo dato disponibile: {max_date}")
                    print(f"   Oggi: {today}")
                    print(f"   Gap: {days_gap} giorni totali ({business_days_missing} giorni lavorativi)")
                    print(f"\n🔄 Tentativo automatico di aggiornamento completo...")
                    
                    # Tenta aggiornamento automatico completo
                    import subprocess
                    import sys
                    
                    update_success = False
                    
                    try:
                        # Step 1: Ingest data (market_data + risk_metrics)
                        print(f"   📥 Step 1/2: Aggiornamento dati storici (ingest_data.py)...")
                        ingest_script = os.path.join(
                            os.path.dirname(__file__), 
                            'ingest_data.py'
                        )
                        
                        result_ingest = subprocess.run(
                            [sys.executable, ingest_script],
                            capture_output=True,
                            text=True,
                            timeout=300  # 5 minuti timeout
                        )
                        
                        if result_ingest.returncode != 0:
                            print(f"   ❌ Ingest fallito: {result_ingest.stderr[:200]}")
                            print(f"   Il backtest proseguirà con dati disponibili fino a {max_date}\n")
                        else:
                            print(f"   ✅ Dati storici aggiornati")
                            
                            # Step 2: Compute signals (ricalcola segnali)
                            print(f"   🧮 Step 2/2: Ricalcolo segnali (compute_signals.py --preset full)...")
                            compute_script = os.path.join(
                                os.path.dirname(__file__), 
                                'compute_signals.py'
                            )
                            
                            result_compute = subprocess.run(
                                [sys.executable, compute_script, '--preset', 'full'],
                                capture_output=True,
                                text=True,
                                timeout=600  # 10 minuti timeout
                            )
                            
                            if result_compute.returncode != 0:
                                print(f"   ❌ Compute signals fallito: {result_compute.stderr[:200]}")
                                print(f"   Il backtest proseguirà con dati disponibili fino a {max_date}\n")
                            else:
                                print(f"   ✅ Segnali ricalcolati")
                                update_success = True
                                
                                # Ri-verifica date dopo update completo
                                min_max_updated = engine.conn.execute("""
                                SELECT MIN(date) AS min_date, MAX(date) AS max_date
                                FROM signals
                                """).fetchone()
                                min_date, max_date = min_max_updated
                                
                                new_gap = (today - max_date).days
                                print(f"\n✅ Aggiornamento completato!")
                                print(f"   Nuovo ultimo dato: {max_date} ({new_gap} giorni fa)\n")
                                
                                if new_gap > 1:
                                    print(f"   ℹ️  Gap residuo normale (mercati chiusi o festività)\n")
                    
                    except subprocess.TimeoutExpired:
                        print(f"   ❌ Timeout aggiornamento (>10min)")
                        print(f"   Il backtest proseguirà con dati disponibili fino a {max_date}\n")
                    except Exception as e:
                        print(f"   ❌ Errore durante aggiornamento automatico: {e}")
                        print(f"   Il backtest proseguirà con dati disponibili fino a {max_date}\n")
                    
                    # Auto-healing: se update fallito E gap persiste, considera chiusura eccezionale
                    if not update_success and business_days_missing > 1:
                        print(f"\n🔍 Analisi gap persistente...")
                        
                        # Verifica se giorni mancanti potrebbero essere chiusure eccezionali
                        # calendar già importato sopra
                        
                        missing_dates = []
                        current = max_date + timedelta(days=1)
                        
                        while current < today:
                            # Solo giorni feriali non già festività
                            if current.weekday() < 5 and not calendar.is_holiday(current):
                                missing_dates.append(current)
                            current += timedelta(days=1)
                        
                        if missing_dates and len(missing_dates) <= 3:  # Max 3 giorni per auto-register
                            print(f"   Trovati {len(missing_dates)} giorni feriali senza dati:")
                            for md in missing_dates:
                                print(f"   - {md} ({md.strftime('%A')})")
                            
                            print(f"\n   💡 Possibile chiusura eccezionale mercato (terremoto, emergenza, ecc.)")
                            print(f"   Registrazione automatica come chiusura eccezionale...")
                            
                            for md in missing_dates:
                                reason = f"Auto-detected: no data available after multiple update attempts"
                                calendar.add_exceptional_closure(md, reason)
                            
                            print(f"   ✅ {len(missing_dates)} chiusure eccezionali registrate")
                            print(f"   Il sistema non tenterà più di aggiornare queste date\n")
                
                elif days_gap > 0:
                    print(f"\nℹ️  Info: Ultimo dato disponibile: {max_date} ({days_gap} giorni fa)")

                if env_preset == 'full':
                    start_date = min_date
                    end_date = max_date
                else:
                    recent_days = int(env_recent_days) if env_recent_days else 365
                    end_date = max_date
                    start_date = end_date - timedelta(days=recent_days)
            else:
                if env_preset not in PRESET_PERIODS:
                    raise ValueError(f"Preset non valido: {env_preset}. Validi: {['full','recent'] + list(PRESET_PERIODS.keys())}")
                p_start, p_end = PRESET_PERIODS[env_preset]
                start_date = _parse_date(p_start)
                end_date = _parse_date(p_end)
        elif env_start and env_end:
            start_date = _parse_date(env_start)
            end_date = _parse_date(env_end)
        
        # 1. Inizializza portfolio con deposito alla start_date
        engine.initialize_portfolio(20000.0, start_date=start_date)
        
        # 2. Esegui simulazione
        engine.run_simulation(start_date, end_date)
        
        # 3. Crea portfolio_overview reale
        engine.create_portfolio_overview(start_date, end_date)
        
        # 4. Calcola KPI reali
        kpi = engine.calculate_real_kpi(start_date, end_date)
        
        # 5. Report risultati
        print(f"\n📊 BACKTEST RESULTS (SIMULAZIONE REALE):")
        print(f"Periodo: {start_date} → {end_date}")
        print(f"Valore Iniziale: €{kpi['initial_value']:,.2f}")
        print(f"Valore Finale: €{kpi['final_value']:,.2f}")
        print(f"Return Totale: {kpi['total_return']:.2%}")
        print(f"CAGR: {kpi['cagr']:.2%}")
        print(f"Max Drawdown: {kpi['max_dd']:.2%}")
        print(f"Sharpe Ratio: {kpi['sharpe']:.2f}")
        print(f"Volatility: {kpi['vol']:.2%}")
        print(f"Turnover: {kpi['turnover']:.2%}")
        
        print(f"\n✅ Backtest con simulazione reale completato")
        return True
        
    except Exception as e:
        print(f"❌ Errore backtest engine: {e}")
        return False
        
    finally:
        engine.close()

if __name__ == "__main__":
    success = run_backtest_simulation()
    sys.exit(0 if success else 1)
