#!/usr/bin/env python3
"""
Backtest Engine - ETF Italia Project v10.8
Simulazione reale con esecuzione ordini e contabilizzazione fiscale
Event-driven day-by-day simulation con SELL→BUY priority
"""

import sys
import os
import json
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows console robustness
from utils.console_utils import setup_windows_console
setup_windows_console()

from orchestration.session_manager import get_session_manager
from trading.execute_orders import check_cash_available, check_position_available
from fiscal.tax_engine import calculate_tax
from trading.strategy_engine_v2 import generate_orders_with_holding_period
from utils.universe_helper import get_cost_model_for_symbol

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
        
        # Usa start_date se fornita; in caso contrario, ancora il deposito alla
        # prima data disponibile in market_data per evitare "future leak" nei
        # backtest (non ha senso avere CASH in ledger oltre l'ultimo close).
        if start_date:
            deposit_date = start_date
        else:
            first_mkt = self.conn.execute("SELECT MIN(date) FROM market_data").fetchone()[0]
            deposit_date = first_mkt if first_mkt else datetime.now().date()
        
        run_id = f"backtest_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        trade_ccy = (self.config.get("settings", {}) or {}).get("currency", "EUR")
        self.conn.execute("""
        INSERT INTO fiscal_ledger (
            id, date, type, symbol, qty, price, fees, tax_paid,
            pmc_snapshot,
            trade_currency, exchange_rate_used, price_eur,
            run_type, run_id, decision_path, reason_code, notes
        ) VALUES (
            ?, ?, 'DEPOSIT', 'CASH', ?, 1.0, 0, 0,
            1.0,
            ?, 1.0, 1.0,
            'BACKTEST', ?, 'SETUP', 'INITIAL_DEPOSIT', 'Initial capital'
        )
        """, [
            next_id,
            deposit_date,
            float(initial_capital),
            trade_ccy,
            run_id
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
        
        # 3. Loop giorno per giorno con strategy_engine_v2 (TWO-PASS)
        for idx, current_date in enumerate(trading_dates):
            if idx % progress_interval == 0:
                print(f"  Processati {idx}/{len(trading_dates)} giorni...")
            
            # 3.1 Genera ordini con strategy_engine_v2 (holding period + portfolio construction)
            result = generate_orders_with_holding_period(
                self.conn,
                self.config,
                current_date=current_date,
                run_type='BACKTEST',
                run_id=None,  # Auto-generato
                underlying_map={}  # Default: no overlap
            )
            
            # 3.2 Esegui ordini SELL (PASS 1)
            for order in result['orders_sell']:
                success = self._execute_order(
                    current_date,
                    order['symbol'],
                    order['action'],
                    int(order['qty']),
                    order['price'],
                    decision_path=order['decision_path'],
                    reason_code=order['reason_code'],
                    run_id=result['run_id']
                )
                if success:
                    executed_orders.append((current_date, order['symbol'], order['action'], int(order['qty']), order['price']))
            
            # 3.3 Esegui ordini BUY (PASS 2)
            for order in result['orders_buy']:
                success = self._execute_order(
                    current_date,
                    order['symbol'],
                    order['action'],
                    int(order['qty']),
                    order['price'],
                    decision_path=order['decision_path'],
                    reason_code=order['reason_code'],
                    run_id=result['run_id'],
                    entry_score=order.get('entry_score'),
                    expected_holding_days=order.get('expected_holding_days'),
                    expected_exit_date=order.get('expected_exit_date')
                )
                if success:
                    executed_orders.append((current_date, order['symbol'], order['action'], int(order['qty']), order['price']))
        
        print(f"✅ Eseguiti {len(executed_orders)} ordini su {len(trading_dates)} giorni")
        
    def _execute_order(self, date, symbol, order_type, qty, price, decision_path='LEGACY', reason_code='LEGACY_ORDER', run_id=None, entry_score=None, expected_holding_days=None, expected_exit_date=None):
        """Esegue singolo ordine con logica fiscale condivisa con execute_orders"""
        
        if run_id is None:
            run_id = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 1. Calcola costi usando configurazione reale (non hard-coded)
        position_value = qty * price
        
        # Ottieni cost model per simbolo
        cost_model = get_cost_model_for_symbol(self.config, symbol)
        
        # Commissione da configurazione
        commission_pct = cost_model['commission_pct']
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
        slippage_bps = cost_model['slippage_bps']
        slippage_bps = max(slippage_bps, volatility * 0.5)  # Volatility adjustment
        slippage = position_value * (slippage_bps / 10000)
        
        total_cost = position_value + commission + slippage
        
        # 2. Pre-trade controls (condivisi con execute_orders)
        if order_type == 'BUY':
            cash_available, cash_balance = check_cash_available(self.conn, total_cost, run_type='BACKTEST')
            if not cash_available:
                print(f"  ❌ {symbol} BUY {qty:.0f} @ €{price:.2f} - CASH INSUFFICIENTE: richiesto €{total_cost:.2f}, disponibile €{cash_balance:.2f}")
                return False  # Ordine rifiutato
        
        elif order_type == 'SELL':
            position_available, current_qty = check_position_available(self.conn, symbol, qty, run_type='BACKTEST')
            if not position_available:
                print(f"  ❌ {symbol} SELL {qty:.0f} @ €{price:.2f} - POSITION INSUFFICIENTE: richiesto {qty:.0f}, disponibile {current_qty:.0f}")
                return False
        
        # Calcola PMC snapshot
        pmc_snapshot = self.conn.execute("""
        SELECT COALESCE(SUM(pmc_snapshot), 0) FROM fiscal_ledger WHERE date < ?
        AND run_type = 'BACKTEST'
        """, [date]).fetchone()[0]
        
        # Calcola tassazione per SELL
        tax_amount = 0.0
        if order_type == 'SELL':
            avg_cost = self.conn.execute("""
            SELECT COALESCE(SUM(qty * price) / SUM(qty), 0) as avg_cost
            FROM fiscal_ledger 
            WHERE symbol = ? AND type = 'BUY' AND date <= ?
            AND run_type = 'BACKTEST'
            """, [symbol, date]).fetchone()[0]
            
            proceeds = qty * price - commission - slippage
            cost_basis = qty * avg_cost
            gain = proceeds - cost_basis
            
            # Calcolo tassazione usando logica condivisa
            tax_result = calculate_tax(gain, symbol, date, self.conn)
            tax_amount = max(0.0, tax_result['tax_amount'])  # Garantisce >= 0 per CHECK constraint
            zainetto_used = tax_result['zainetto_used']
            explanation = tax_result['explanation']
        
        # INSERT completo con tutti i parametri audit
        trade_currency = self.config['settings']['currency']
        exchange_rate = 1.0
        exec_mode = self.config.get('execution', {}).get('execution_price_mode', 'CLOSE_SAME_DAY_SLIPPAGE')
        
        next_id = self.conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM fiscal_ledger").fetchone()[0]
        
        # INSERT con campi audit obbligatori (FIX BUG #8: aggiungi trade_currency)
        self.conn.execute("""
        INSERT INTO fiscal_ledger (
            id, date, type, symbol, qty, price, fees, tax_paid,
            pmc_snapshot, trade_currency, exchange_rate_used, price_eur, 
            run_id, run_type, decision_path, reason_code, execution_price_mode,
            entry_score, expected_holding_days, expected_exit_date,
            notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            next_id, date, order_type, symbol, qty, price, 
            commission + slippage, tax_amount,
            pmc_snapshot, trade_currency, exchange_rate, price, 
            run_id, 'BACKTEST',
            decision_path, reason_code, exec_mode,
            entry_score, expected_holding_days, expected_exit_date,
            'Backtest execution', datetime.now()
        ])
        
        return True
    
    def calculate_portfolio_value(self, date):
        """Calcola valore portfolio alla data specifica"""
        
        # Posizioni aperte
        positions = self.conn.execute("""
        SELECT 
            fl.symbol,
            SUM(CASE WHEN fl.type = 'BUY' THEN fl.qty ELSE -fl.qty END) as net_qty,
            (
                SELECT md2.close
                FROM market_data md2
                WHERE md2.symbol = fl.symbol
                AND md2.date <= ?
                ORDER BY md2.date DESC
                LIMIT 1
            ) as current_price
        FROM fiscal_ledger fl
        WHERE fl.date <= ?
        AND fl.type IN ('BUY', 'SELL')
        AND fl.run_type = 'BACKTEST'
        GROUP BY fl.symbol
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
        
        # Crea tabella persistente con posizioni cumulative corrette (no duplicati)
        self.conn.execute("""
        CREATE TABLE daily_portfolio AS
        WITH trading_dates AS (
            SELECT DISTINCT date 
            FROM market_data 
            WHERE date BETWEEN ? AND ?
        ),
        position_changes AS (
            SELECT 
                date,
                symbol,
                SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as qty_change
            FROM fiscal_ledger
            WHERE run_type = 'BACKTEST'
            AND type IN ('BUY', 'SELL')
            GROUP BY date, symbol
        ),
        daily_positions AS (
            SELECT 
                td.date,
                symbols.symbol,
                COALESCE(SUM(COALESCE(pc.qty_change, 0)) OVER (
                    PARTITION BY symbols.symbol 
                    ORDER BY td.date 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ), 0) as cumulative_qty
            FROM trading_dates td
            CROSS JOIN (SELECT DISTINCT symbol FROM position_changes) symbols
            LEFT JOIN position_changes pc ON td.date = pc.date AND symbols.symbol = pc.symbol
        )
        SELECT 
            dp.date,
            dp.symbol,
            md.adj_close,
            md.volume,
            dp.cumulative_qty * md.close as market_value,
            dp.cumulative_qty as qty,
            0 as cash
        FROM daily_positions dp
        JOIN market_data md
          ON md.symbol = dp.symbol
         AND md.date = (
             SELECT MAX(md2.date)
             FROM market_data md2
             WHERE md2.symbol = dp.symbol
               AND md2.date <= dp.date
         )
        WHERE dp.cumulative_qty > 0
        ORDER BY dp.date, dp.symbol
        """, [start_date, end_date])
        
        # Crea vista portfolio_overview basata su tabella persistente
        self.conn.execute("""
        CREATE OR REPLACE VIEW portfolio_overview AS
        SELECT * FROM daily_portfolio
        ORDER BY date, symbol
        """)
        
        print("✅ portfolio_overview creato da dati reali")
    
    def calculate_real_kpi(self, start_date, end_date):
        """Calcola KPI basati su simulazione reale"""
        
        # Ottieni valori portfolio sulle sole trading dates (coerente con signals/market_data)
        portfolio_values = []
        trading_dates = self.conn.execute("""
        SELECT DISTINCT date
        FROM signals
        WHERE date BETWEEN ? AND ?
        ORDER BY date
        """, [start_date, end_date]).fetchall()
        trading_dates = [d[0] for d in trading_dates]

        for d in trading_dates:
            try:
                value = self.calculate_portfolio_value(d)
                portfolio_values.append((d, value))
            except Exception:
                continue
        
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
    
    print("🚀 BACKTEST ENGINE - ETF Italia Project v10.8")
    print("=" * 60)
    
    # Path configurazione (usa path_manager per coerenza)
    from utils.path_manager import get_path_manager
    
    pm = get_path_manager()
    config_path = str(pm.etf_universe_path)
    db_path = str(pm.db_path)
    
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
                        from pathlib import Path

                        project_root = Path(__file__).resolve().parents[2]
                        ingest_script = str(project_root / 'scripts' / 'data' / 'ingest_data.py')
                        
                        env = os.environ.copy()
                        env.setdefault("PYTHONUTF8", "1")
                        env.setdefault("PYTHONIOENCODING", "utf-8")

                        result_ingest = subprocess.run(
                            [sys.executable, ingest_script],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=300,  # 5 minuti timeout
                            env=env,
                        )
                        
                        if result_ingest.returncode != 0:
                            print(f"   ❌ Ingest fallito: {result_ingest.stderr[:200]}")
                            print(f"   Il backtest proseguirà con dati disponibili fino a {max_date}\n")
                        else:
                            print(f"   ✅ Dati storici aggiornati")
                            
                            # Step 2: Compute signals (ricalcola segnali)
                            print(f"   🧮 Step 2/2: Ricalcolo segnali (compute_signals.py --preset full)...")
                            compute_script = str(project_root / 'scripts' / 'data' / 'compute_signals.py')
                            
                            result_compute = subprocess.run(
                                [sys.executable, compute_script, '--preset', 'full'],
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=600,  # 10 minuti timeout
                                env=env,
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

        signal_bounds = engine.conn.execute("""
        SELECT MIN(date) AS min_date, MAX(date) AS max_date
        FROM signals
        WHERE date BETWEEN ? AND ?
        """, [start_date, end_date]).fetchone()

        sb_min, sb_max = signal_bounds
        if sb_min is None or sb_max is None:
            raise ValueError("Nessun segnale disponibile nel range selezionato")

        start_date = sb_min
        end_date = sb_max
        
        # 1. Inizializza portfolio con deposito alla start_date
        engine.initialize_portfolio(20000.0, start_date=start_date)
        
        # 2. Esegui simulazione
        engine.run_simulation(start_date, end_date)
        
        # 3. Crea portfolio_overview reale
        engine.create_portfolio_overview(start_date, end_date)
        
        # 4. Calcola KPI reali
        kpi = engine.calculate_real_kpi(start_date, end_date)
        
        # 5. Salva risultati in data/backtests/runs/
        from utils.path_manager import get_path_manager
        pm = get_path_manager()
        
        # Genera run_id e determina preset
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preset_name = env_preset if env_preset else 'custom'
        run_id = f"backtest_{preset_name}_{timestamp}"
        preset = preset_name
        
        # Crea directory run
        run_dir = pm.backtest_run_dir(preset, timestamp)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Salva KPI (converti date in stringhe per JSON)
        kpi_serializable = {k: (str(v) if isinstance(v, (datetime, timedelta)) else v) for k, v in kpi.items()}
        kpi_file = pm.backtest_kpi_path(preset, timestamp)
        with open(kpi_file, 'w') as f:
            json.dump(kpi_serializable, f, indent=2)
        
        # Salva orders eseguiti
        orders_executed = engine.conn.execute("""
        SELECT symbol, type, qty, price, fees, tax_paid, date, notes
        FROM fiscal_ledger
        WHERE run_type = 'BACKTEST'
        AND type IN ('BUY', 'SELL')
        ORDER BY date, id
        """).fetchall()
        
        orders_data = {
            'backtest_id': run_id,
            'preset': preset,
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_orders': len(orders_executed),
            'orders': [
                {
                    'symbol': o[0],
                    'type': o[1],
                    'qty': float(o[2]),
                    'price': float(o[3]),
                    'fees': float(o[4]),
                    'tax': float(o[5]),
                    'date': str(o[6]),
                    'notes': o[7]
                }
                for o in orders_executed
            ]
        }
        
        orders_file = pm.backtest_orders_path(preset, timestamp)
        with open(orders_file, 'w') as f:
            json.dump(orders_data, f, indent=2)
        
        # Salva portfolio evolution
        portfolio_evolution = engine.conn.execute("""
        WITH daily_positions AS (
            SELECT 
                date,
                symbol,
                SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) as position
            FROM fiscal_ledger
            WHERE run_type = 'BACKTEST'
            AND type IN ('BUY', 'SELL')
            GROUP BY date, symbol
        )
        SELECT 
            date,
            symbol,
            SUM(position) OVER (PARTITION BY symbol ORDER BY date) as cumulative_position
        FROM daily_positions
        ORDER BY date, symbol
        """).fetchall()
        
        portfolio_data = {
            'backtest_id': run_id,
            'preset': preset,
            'period': {'start': str(start_date), 'end': str(end_date)},
            'evolution': {}
        }
        
        for date, symbol, position in portfolio_evolution:
            date_str = str(date)
            if date_str not in portfolio_data['evolution']:
                portfolio_data['evolution'][date_str] = {}
            portfolio_data['evolution'][date_str][symbol] = float(position)
        
        portfolio_file = pm.backtest_portfolio_path(preset, timestamp)
        with open(portfolio_file, 'w') as f:
            json.dump(portfolio_data, f, indent=2)
        
        # Salva trades summary
        trades_summary = {
            'backtest_id': run_id,
            'preset': preset,
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_trades': len([o for o in orders_executed if o[1] in ['BUY', 'SELL']]),
            'buy_trades': len([o for o in orders_executed if o[1] == 'BUY']),
            'sell_trades': len([o for o in orders_executed if o[1] == 'SELL']),
            'total_fees': sum(o[4] for o in orders_executed),
            'total_tax': sum(o[5] for o in orders_executed)
        }
        
        trades_file = pm.backtest_trades_path(preset, timestamp)
        with open(trades_file, 'w') as f:
            json.dump(trades_summary, f, indent=2)
        
        # 6. Report risultati
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
        print(f"\n📁 Output salvati in: {run_dir}")
        print(f"   - kpi.json: {kpi_file.name}")
        print(f"   - orders.json: {orders_file.name}")
        print(f"   - portfolio.json: {portfolio_file.name}")
        print(f"   - trades.json: {trades_file.name}")
        
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


