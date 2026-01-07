#!/usr/bin/env python3
"""
Compute Signals - ETF Italia Project v10
Signal Engine per generazione segnali oggettivi secondo DIPF §4
"""

import sys
import os
import json
import duckdb
import pandas as pd
import numpy as np

from datetime import datetime, timedelta
from itertools import chain
import argparse
import io
import bisect
import time

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.path_manager import get_path_manager

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

PRESET_PERIODS = {
    'full': ('DYNAMIC', 'DYNAMIC'),
    'recent': ('DYNAMIC', 'DYNAMIC'),
    'covid': ('2020-01-01', '2021-12-31'),
    'gfc': ('2007-01-01', '2010-12-31'),
    'eurocrisis': ('2011-01-01', '2013-12-31'),
    'inflation2022': ('2021-10-01', '2023-03-31'),
}


def _parse_date(s):
    if s is None:
        return None
    return datetime.strptime(s, '%Y-%m-%d').date()


def compute_signals(start_date=None, end_date=None, preset=None, lookback_days=60, recent_days=365):
    """Calcola segnali per universo ETF"""
    
    print(" COMPUTE SIGNALS - ETF Italia Project v10")
    print("=" * 60)
    
    pm = get_path_manager()
    config_path = str(pm.etf_universe_path)
    pm = get_path_manager()
    db_path = str(pm.db_path)
    
    # Carica configurazione
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    conn = duckdb.connect(db_path)
    
    try:
        # Inizia transazione
        conn.execute("BEGIN TRANSACTION")
        
        # 1. Setup Signal Engine
        print(" Setup Signal Engine...")
        
        # Crea tabella signals se non esiste
        conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY,
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            signal_state VARCHAR NOT NULL CHECK (signal_state IN ('RISK_ON', 'RISK_OFF', 'HOLD')),
            risk_scalar DOUBLE CHECK (risk_scalar >= 0 AND risk_scalar <= 1),
            explain_code VARCHAR,
            sma_200 DOUBLE,
            volatility_20d DOUBLE,
            spy_guard BOOLEAN DEFAULT FALSE,
            regime_filter VARCHAR DEFAULT 'NEUTRAL',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, symbol)
        )
        """)
        
        # Crea indici
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_date_symbol ON signals(date, symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_state ON signals(signal_state)")
        
        print(" Signal Engine ready")
        
        # 2. Ottieni simboli universe
        symbols = []
        symbols.extend([etf['symbol'] for etf in config['universe']['core']])
        symbols.extend([etf['symbol'] for etf in config['universe']['satellite']])
        
        # Aggiungi bond se presenti (per diversificazione operativa)
        if 'bond' in config['universe']:
            bond_symbols = [etf['symbol'] for etf in config['universe']['bond']]
            symbols.extend(bond_symbols)
            print(f" Bond symbols added: {bond_symbols}")
        
        print(f" Processing symbols: {symbols}")

        # Pre-build Spy Guard cache (massive speedup on FULL/ALL)
        spy_guard_cache = _build_spy_guard_cache(conn, config)
        
        # 3. Calcola segnali per ogni simbolo
        total_signals = 0
        
        # Resolve range (static presets here; dynamic presets handled per-symbol)
        if preset and preset not in ('full', 'recent'):
            if preset not in PRESET_PERIODS:
                raise ValueError(f"Preset non valido: {preset}. Validi: {list(PRESET_PERIODS.keys())}")
            preset_start, preset_end = PRESET_PERIODS[preset]
            start_date = _parse_date(preset_start)
            end_date = _parse_date(preset_end)

        for symbol in symbols:
            print(f"\n Computing signals for {symbol}")
            
            # Resolve per-symbol dynamic presets
            local_start = start_date
            local_end = end_date

            if preset == 'full':
                min_max = conn.execute(
                    "SELECT MIN(date) as min_date, MAX(date) as max_date FROM risk_metrics WHERE symbol = ?",
                    [symbol],
                ).fetchone()
                if min_max:
                    local_start, local_end = min_max
            elif preset == 'recent':
                max_date = conn.execute(
                    "SELECT MAX(date) FROM risk_metrics WHERE symbol = ?",
                    [symbol],
                ).fetchone()[0]
                if max_date is not None:
                    local_end = max_date
                    local_start = local_end - timedelta(days=int(recent_days))

            # Ottieni dati con metriche (default: finestra recente; oppure range esplicito)
            if local_start is not None and local_end is not None:
                metrics_query = """
                SELECT 
                    date,
                    adj_close,
                    sma_200,
                    volatility_20d,
                    drawdown_pct,
                    daily_return
                FROM risk_metrics 
                WHERE symbol = ?
                  AND date BETWEEN ? AND ?
                ORDER BY date ASC
                """
                df = conn.execute(metrics_query, [symbol, local_start, local_end]).fetchdf()
            else:
                metrics_query = """
                SELECT 
                    date,
                    adj_close,
                    sma_200,
                    volatility_20d,
                    drawdown_pct,
                    daily_return
                FROM risk_metrics 
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT ?
                """
                df = conn.execute(metrics_query, [symbol, int(lookback_days)]).fetchdf()

            if df.empty:
                print(f"   ️ No data available for {symbol}")
                continue

            # Se query era DESC (default), rimetti in ASC per calcolo coerente
            df = df.sort_values('date')
            
            # Calcola segnali per ogni data
            signals_data = []

            # Pre-build entry price cache (avoid per-row ledger queries)
            entry_price_at_date = _build_entry_price_at_date(conn, symbol)

            total_rows = len(df)
            loop_start_ts = time.time()
            last_heartbeat_ts = loop_start_ts

            for i, row in enumerate(df.itertuples(index=False), start=1):
                # Progress line every 1000 rows
                if i % 1000 == 0:
                    now = time.time()
                    pct = (i / total_rows) * 100 if total_rows else 0
                    elapsed = now - loop_start_ts
                    print(f"    progress: {i}/{total_rows} ({pct:.1f}%) elapsed={elapsed:.1f}s", flush=True)

                signal_date = row.date
                current_price = row.adj_close
                sma_200 = row.sma_200
                volatility_20d = row.volatility_20d
                drawdown_pct = row.drawdown_pct
                
                # Inizializza variabili segnale
                signal_state = 'HOLD'
                risk_scalar = 1.0
                explain_code = 'NEUTRAL'
                spy_guard = False
                regime_filter = 'NEUTRAL'
                
                # 3.1 Trend Following Signal (SMA 200)
                if pd.notna(sma_200):
                    if current_price > sma_200 * 1.02:  # 2% above SMA
                        signal_state = 'RISK_ON'
                        explain_code = 'TREND_UP_SMA200'
                    elif current_price < sma_200 * 0.98:  # 2% below SMA
                        signal_state = 'RISK_OFF'
                        explain_code = 'TREND_DOWN_SMA200'
                
                # 3.5 Entry-Aware Stop-Loss Check (after trend but before other filters)
                entry_price = entry_price_at_date(signal_date)
                if entry_price:
                    stop_action, stop_reason = check_entry_aware_stop_loss(config, symbol, current_price, entry_price, volatility_20d)
                    if stop_action:
                        signal_state = stop_action
                        explain_code = stop_reason
                        risk_scalar = 0.0
                        print(f"    STOP entry-aware: {stop_reason}")

                # 3.6 Volatility Regime Filter
                if pd.notna(volatility_20d):
                    vol_threshold = config['risk_management']['volatility_breaker']
                    if volatility_20d > vol_threshold:
                        regime_filter = 'HIGH_VOL'
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 0.5  # Halve size in high vol
                            explain_code += '_VOL_ADJ'
                    elif volatility_20d < 0.10:
                        regime_filter = 'LOW_VOL'
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 1.2  # Increase size in low vol
                            explain_code += '_VOL_BOOST'
                
                # 3.7 Drawdown Protection
                if pd.notna(drawdown_pct):
                    if drawdown_pct < -0.15:  # 15% drawdown
                        signal_state = 'RISK_OFF'
                        explain_code = 'DRAWDOWN_PROTECT'
                        risk_scalar = 0.0
                    elif drawdown_pct < -0.10:  # 10% drawdown
                        if signal_state == 'RISK_ON':
                            risk_scalar *= 0.7
                            explain_code += '_DD_ADJ'
                
                # 3.8 Spy Guard (per tutti i simboli)
                spy_guard_active = _spy_guard_active_from_cache(spy_guard_cache, signal_date)
                spy_guard = spy_guard_active
                
                if spy_guard_active:
                    if signal_state == 'RISK_ON':
                        signal_state = 'RISK_OFF'
                        explain_code = 'SPY_GUARD_BLOCK'
                        risk_scalar = 0.0
                    regime_filter = 'BEAR_MARKET'
                
                # 3.9 Risk Scalar Volatility Targeting
                target_vol = config['settings']['volatility_target']  # 15%
                if pd.notna(volatility_20d) and volatility_20d > 0:
                    vol_scalar = target_vol / volatility_20d
                    vol_scalar = min(1.0, vol_scalar)  # Cap at 1.0
                    vol_scalar = max(config['risk_management']['risk_scalar_floor'], vol_scalar)  # Floor
                    
                    risk_scalar *= vol_scalar
                
                # Arrotonda risk scalar
                risk_scalar = round(risk_scalar, 3)
                risk_scalar = max(0.0, min(1.0, risk_scalar))
                
                signals_data.append({
                    'date': signal_date,
                    'symbol': symbol,
                    'signal_state': signal_state,
                    'risk_scalar': risk_scalar,
                    'explain_code': explain_code,
                    'sma_200': sma_200,
                    'volatility_20d': volatility_20d,
                    'spy_guard': spy_guard,
                    'regime_filter': regime_filter
                })
            
            # Insert signals nel database con UPSERT
            if signals_data:
                # Ottieni prossimo ID disponibile per evitare conflitti
                next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM signals").fetchone()[0]
                
                # Usa UPSERT di DuckDB (INSERT OR REPLACE)
                signals_to_insert = []
                for i, signal in enumerate(signals_data):
                    signals_to_insert.append((
                        next_id + i,  # ID esplicito
                        signal['date'],
                        signal['symbol'],
                        signal['signal_state'],
                        signal['risk_scalar'],
                        signal['explain_code'],
                        signal['sma_200'],
                        signal['volatility_20d'],
                        signal['spy_guard'],
                        signal['regime_filter'],
                        datetime.now()
                    ))
                
                # DuckDB richiede un target esplicito per DO UPDATE quando esistono più vincoli UNIQUE/PK
                conn.executemany("""
                INSERT INTO signals (id, date, symbol, signal_state, risk_scalar, explain_code, sma_200, volatility_20d, spy_guard, regime_filter, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (date, symbol) DO UPDATE SET
                    signal_state = excluded.signal_state,
                    risk_scalar = excluded.risk_scalar,
                    explain_code = excluded.explain_code,
                    sma_200 = excluded.sma_200,
                    volatility_20d = excluded.volatility_20d,
                    spy_guard = excluded.spy_guard,
                    regime_filter = excluded.regime_filter,
                    created_at = excluded.created_at
                WHERE
                    signals.signal_state IS DISTINCT FROM excluded.signal_state
                    OR signals.risk_scalar IS DISTINCT FROM excluded.risk_scalar
                    OR signals.explain_code IS DISTINCT FROM excluded.explain_code
                    OR signals.sma_200 IS DISTINCT FROM excluded.sma_200
                    OR signals.volatility_20d IS DISTINCT FROM excluded.volatility_20d
                    OR signals.spy_guard IS DISTINCT FROM excluded.spy_guard
                    OR signals.regime_filter IS DISTINCT FROM excluded.regime_filter
                """, signals_to_insert)
                
                print(f"    {symbol}: {len(signals_data)} signals upserted")
                total_signals += len(signals_data)
        
        # 4. Report segnali correnti
        print(f"\n CURRENT SIGNALS SNAPSHOT")
        print("-" * 40)
        
        current_signals_query = """
        SELECT symbol, signal_state, risk_scalar, explain_code, 
               sma_200, volatility_20d, spy_guard, regime_filter
        FROM signals 
        WHERE date = (SELECT MAX(date) FROM signals)
        ORDER BY symbol
        """
        
        current_signals = conn.execute(current_signals_query).fetchall()
        
        for signal in current_signals:
            symbol, state, scalar, explain, sma, vol, spy_guard, regime = signal
            
            emoji = "" if state == "RISK_ON" else "" if state == "RISK_OFF" else ""
            guard_emoji = "️" if spy_guard else ""
            
            # Handle None values safely
            explain_str = explain if explain else "N/A"
            vol_str = f"{vol:.1%}" if vol is not None else "N/A"
            regime_str = regime if regime else "N/A"
            
            print(f"{emoji} {symbol}: {state} (scalar: {scalar:.3f}) {guard_emoji}")
            print(f"    {explain_str} | Vol: {vol_str} | Regime: {regime_str}")
        
        # 5. Summary statistics
        print(f"\n SIGNALS SUMMARY")
        print("-" * 40)
        
        summary_query = """
        SELECT 
            signal_state,
            COUNT(*) as count,
            AVG(risk_scalar) as avg_scalar
        FROM signals 
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY signal_state
        """
        
        summary = conn.execute(summary_query).fetchall()
        
        for state, count, avg_scalar in summary:
            emoji = "" if state == "RISK_ON" else "" if state == "RISK_OFF" else ""
            print(f"{emoji} {state}: {count} signals (avg scalar: {avg_scalar:.3f})")
        
        print(f"\n SIGNALS COMPUTATION COMPLETED")
        print(f" Total signals processed: {total_signals}")
        
        # Commit transazione
        conn.commit()
        
        return True
        
    except Exception as e:
        print(f" Errore compute signals: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
        
    finally:
        conn.close()


def _build_spy_guard_cache(conn, config):
    """Preload SPY guard series once (avoid per-row DB queries)."""
    if not config.get('risk_management', {}).get('spy_guard_enabled', False):
        return None

    try:
        df_spy = conn.execute(
            """
            SELECT date, adj_close, sma_200
            FROM risk_metrics
            WHERE symbol = '^GSPC'
            ORDER BY date ASC
            """
        ).fetchdf()

        if df_spy.empty:
            return None

        # Keep only rows with SMA
        df_spy = df_spy[pd.notna(df_spy['sma_200'])].copy()
        if df_spy.empty:
            return None

        # Convert dates to python date
        dates = [d.date() if hasattr(d, 'date') else d for d in df_spy['date'].tolist()]
        bear_flags = [(float(ac) < float(sma)) for ac, sma in zip(df_spy['adj_close'].tolist(), df_spy['sma_200'].tolist())]
        return (dates, bear_flags)
    except Exception:
        return None


def _spy_guard_active_from_cache(cache, signal_date):
    if cache is None:
        return False

    dates, flags = cache
    if signal_date is None:
        return False

    d = signal_date.date() if hasattr(signal_date, 'date') else signal_date
    pos = bisect.bisect_right(dates, d) - 1
    if pos < 0:
        return False
    return bool(flags[pos])


def _build_entry_price_at_date(conn, symbol):
    """Build O(N) entry price lookup using one ledger scan (avoid per-row DB queries)."""

    try:
        events = conn.execute(
            """
            SELECT date, type, qty, price
            FROM fiscal_ledger
            WHERE symbol = ? AND type IN ('BUY', 'SELL')
            ORDER BY date ASC
            """,
            [symbol],
        ).fetchall()
    except Exception:
        events = []

    # Fast path: no events => always None
    if not events:
        def _none(_d):
            return None
        return _none

    # Two-pointer over events
    j = 0
    qty = 0.0
    avg_price = 0.0

    def _advance_to(d):
        nonlocal j, qty, avg_price

        dd = d.date() if hasattr(d, 'date') else d
        while j < len(events):
            ev_date, ev_type, ev_qty, ev_price = events[j]
            ev_d = ev_date.date() if hasattr(ev_date, 'date') else ev_date
            if ev_d > dd:
                break

            q = float(ev_qty)
            p = float(ev_price)

            if ev_type == 'BUY':
                new_qty = qty + q
                if new_qty > 0:
                    avg_price = ((avg_price * qty) + (p * q)) / new_qty if qty > 0 else p
                qty = new_qty
            else:  # SELL
                qty = qty - q
                if qty <= 0:
                    qty = 0.0
                    avg_price = 0.0

            j += 1

        return avg_price if qty > 0 else None

    return _advance_to

def check_position_entry_price(conn, symbol, date):
    """Ottiene prezzo di entrata per posizione esistente"""
    try:
        entry_query = """
        SELECT AVG(CASE WHEN type = 'BUY' THEN price ELSE NULL END) as avg_buy_price
        FROM fiscal_ledger 
        WHERE symbol = ? 
        AND type IN ('BUY', 'SELL')
        AND date <= ?
        GROUP BY symbol
        HAVING SUM(CASE WHEN type = 'BUY' THEN qty ELSE -qty END) != 0
        """
        result = conn.execute(entry_query, [symbol, date]).fetchone()
        return result[0] if result and result[0] else None
    except Exception:
        return None

def check_entry_aware_stop_loss(config, symbol, current_price, entry_price, volatility_20d):
    """Verifica stop-loss entry-aware basato su prezzo di entrata"""
    if entry_price is None or entry_price <= 0:
        return None, None
    
    # PnL percentage from entry
    pnl_pct = (current_price - entry_price) / entry_price
    
    # Get appropriate stop-loss based on symbol type
    if symbol == 'XS2L.MI':
        stop_loss = config['risk_management'].get('xs2l_stop_loss', -0.15)
        trailing_stop = config['risk_management'].get('xs2l_trailing_stop', -0.10)
    else:
        stop_loss = config['risk_management'].get('stop_loss_satellite', -0.15)
        trailing_stop = config['risk_management'].get('trailing_stop_satellite', -0.10)
    
    # Adjust stop-loss based on volatility (more volatile = wider stop)
    if volatility_20d and volatility_20d > 0.2:  # High volatility
        stop_loss *= 1.5  # 50% wider stop
        trailing_stop *= 1.5
    
    # Check stop-loss
    if pnl_pct <= stop_loss:
        return 'RISK_OFF', f'STOP_LOSS_ENTRY_{pnl_pct:.1%}'
    
    # Check trailing stop
    if pnl_pct <= trailing_stop:
        return 'RISK_OFF', f'TRAILING_STOP_ENTRY_{pnl_pct:.1%}'
    
    return None, None

def check_spy_guard(conn, date, config):
    """Verifica Spy Guard per data specifica"""
    
    if not config['risk_management']['spy_guard_enabled']:
        return False
    
    try:
        # Ottieni S&P 500 SMA 200
        spy_query = """
        SELECT adj_close, sma_200
        FROM risk_metrics 
        WHERE symbol = '^GSPC' AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """
        
        spy_data = conn.execute(spy_query, [date]).fetchone()
        
        if spy_data and spy_data[1] is not None:
            spy_close, spy_sma = spy_data
            return spy_close < spy_sma  # Bear market if below SMA 200
        
    except Exception:
        pass
    
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Compute Signals - ETF Italia Project')
    parser.add_argument('--start-date', type=str, default=None, help='Data inizio (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None, help='Data fine (YYYY-MM-DD)')
    parser.add_argument('--preset', type=str, default=None, help=f"Preset periodo: {list(PRESET_PERIODS.keys())}")
    parser.add_argument('--lookback-days', type=int, default=60, help='Default window size quando non si usa range/preset')
    parser.add_argument('--recent-days', type=int, default=365, help='Finestra giorni per preset recent (rolling)')
    parser.add_argument('--all', action='store_true', help='Esegui signals per full + recent + periodi critici (presets)')
    args = parser.parse_args()

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)

    if args.all:
        preset_order = ['full', 'recent', 'gfc', 'eurocrisis', 'covid', 'inflation2022']
        preset_order = [p for p in preset_order if p in PRESET_PERIODS]
        ok_all = True
        for p in preset_order:
            print("\n" + "=" * 60)
            print(f"ALL MODE - preset={p}")
            print("=" * 60)
            ok_all = compute_signals(preset=p, lookback_days=args.lookback_days, recent_days=args.recent_days) and ok_all
            # Small delay to ensure DB lock is released on Windows
            time.sleep(0.5)
        success = ok_all
    else:
        success = compute_signals(
            start_date=start_date,
            end_date=end_date,
            preset=args.preset,
            lookback_days=args.lookback_days,
            recent_days=args.recent_days,
        )
    sys.exit(0 if success else 1)
