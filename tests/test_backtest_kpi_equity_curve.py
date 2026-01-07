#!/usr/bin/env python3
"""Test Backtest KPI Equity Curve - ETF Italia Project v10

Validazione minima che i KPI backtest siano calcolati su equity curve reale
(cash + market value) e che non esplodano per bug di join/aggregazioni.
"""

import sys
import os
import duckdb

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

from backtest.backtest_runner import calculate_kpi


def _setup_db(tmp_path):
    db_path = os.path.join(tmp_path, 'test_backtest_kpi.duckdb')
    conn = duckdb.connect(db_path)

    conn.execute("""
    CREATE TABLE fiscal_ledger (
        id INTEGER,
        date DATE,
        type VARCHAR,
        symbol VARCHAR,
        qty DOUBLE,
        price DOUBLE,
        fees DOUBLE,
        tax_paid DOUBLE,
        run_type VARCHAR
    )
    """)

    conn.execute("""
    CREATE TABLE market_data (
        symbol VARCHAR,
        date DATE,
        close DOUBLE,
        adj_close DOUBLE,
        volume BIGINT
    )
    """)

    conn.execute("""
    CREATE TABLE signals (
        date DATE,
        symbol VARCHAR,
        signal_state VARCHAR,
        risk_scalar DOUBLE
    )
    """)

    # 2 giorni di trading
    conn.execute("INSERT INTO signals VALUES ('2025-01-02','AAA','RISK_ON',1.0)")
    conn.execute("INSERT INTO signals VALUES ('2025-01-03','AAA','RISK_ON',1.0)")

    conn.execute("INSERT INTO market_data VALUES ('AAA','2025-01-02',100,100,1000)")
    conn.execute("INSERT INTO market_data VALUES ('AAA','2025-01-03',110,110,1000)")

    # deposito + buy 1 quota
    conn.execute("INSERT INTO fiscal_ledger VALUES (1,'2025-01-02','DEPOSIT','CASH',1,1000,0,0,'BACKTEST')")
    conn.execute("INSERT INTO fiscal_ledger VALUES (2,'2025-01-02','BUY','AAA',1,100,0,0,'BACKTEST')")

    conn.commit()
    return conn


def test_backtest_kpi_equity_curve_is_reasonable(tmp_path):
    conn = _setup_db(tmp_path)
    try:
        config = {'universe': {'benchmark': [{'symbol': 'AAA'}]}}
        kpi = calculate_kpi(conn, config, start_date='2025-01-02', end_date='2025-01-03')

        # Con solo 2 giorni, CAGR non importante; controlliamo che non esploda
        assert kpi['vol'] < 5.0
        assert kpi['max_dd'] <= 0.0
        assert kpi['turnover'] >= 0.0
    finally:
        conn.close()
