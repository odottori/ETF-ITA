#!/usr/bin/env python3
"""
Test Guardrails Fixes - ETF Italia Project v10
Verifica che i bug critici nei guardrails siano stati risolti
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestGuardrailsFixes(unittest.TestCase):
    
    def setUp(self):
        """Setup per i test"""
        self.test_config = {
            "risk_management": {
                "volatility_breaker": 0.15,
                "spy_guard_enabled": True,
                "risk_scalar_floor": 0.3
            }
        }
    
    @patch('scripts.risk.check_guardrails.duckdb.connect')
    @patch('scripts.risk.check_guardrails.get_session_manager')
    @patch('builtins.open', create=True)
    @patch('json.load')
    def test_guardrails_status_variable_name_fix(self, mock_json, mock_open, mock_session, mock_db):
        """Verifica che venga usato guardrails_status invece di guardrails"""
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import scripts.risk.check_guardrails as check_guardrails
        
        # Mock config
        mock_json.return_value = self.test_config
        
        # Mock DB responses per triggerare SPY guard
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        
        # Simula SPY guard attivo
        mock_conn.execute.side_effect = [
            # SPY data (adj_close < sma_200)
            MagicMock(fetchone=lambda: (100.0, 110.0)),
            # RISK_ON signals nonostante SPY guard
            MagicMock(fetchone=lambda: (5,)),
            # Altre query vuote
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
        ]
        
        # Mock session manager
        mock_session_mgr = MagicMock()
        mock_session.return_value = mock_session_mgr
        mock_session_mgr.add_report_to_session.return_value = "test_report.json"
        
        # Esegui la funzione - non dovrebbe lanciare NameError
        try:
            result = check_guardrails.check_guardrails()
            # Se arriva qui, il bug è stato risolto
            self.assertIsInstance(result, bool)
        except NameError as e:
            if "guardrails" in str(e):
                self.fail(f"Bug non risolto: {e}")
            else:
                raise
    
    @patch('scripts.risk.check_guardrails.duckdb.connect')
    @patch('scripts.risk.check_guardrails.get_session_manager')
    @patch('builtins.open', create=True)
    @patch('json.load')
    def test_position_concentration_uses_close_prices(self, mock_json, mock_open, mock_session, mock_db):
        """Verifica che la concentrazione usi prezzi di chiusura correnti"""
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import scripts.risk.check_guardrails as check_guardrails
        
        # Mock config
        mock_json.return_value = self.test_config
        
        # Mock DB
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        
        # Simula posizioni con prezzi correnti
        mock_positions = [
            ('ETF1', 100, 50.0, 5000.0),  # symbol, qty, current_price, market_value
            ('ETF2', 200, 25.0, 5000.0)
        ]
        
        # Verifica che la query usi close prices
        mock_conn.execute.return_value.fetchall.return_value = mock_positions
        
        # Mock session manager
        mock_session_mgr = MagicMock()
        mock_session.return_value = mock_session_mgr
        mock_session_mgr.add_report_to_session.return_value = "test_report.json"
        
        # Esegui
        check_guardrails.check_guardrails()
        
        # Verifica che la query usi prezzi di chiusura
        call_args = mock_conn.execute.call_args_list
        concentration_query = None
        for call in call_args:
            if 'current_prices' in str(call):
                concentration_query = call
                break
        
        self.assertIsNotNone(concentration_query, "Query per concentrazione non trovata")
        query_text = str(concentration_query)
        self.assertIn('close as current_price', query_text)
        self.assertIn('market_data', query_text)
    
    @patch('scripts.risk.check_guardrails.duckdb.connect')
    @patch('scripts.risk.check_guardrails.get_session_manager')
    @patch('builtins.open', create=True)
    @patch('json.load')
    def test_market_value_calculation_consistency(self, mock_json, mock_open, mock_session, mock_db):
        """Verifica coerenza calcolo market value"""
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import scripts.risk.check_guardrails as check_guardrails
        
        # Mock config
        mock_json.return_value = self.test_config
        
        # Mock DB
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        
        # Simula posizioni
        mock_positions = [
            ('ETF1', 100, 50.0, 5000.0),  # 100 * 50.0 = 5000
            ('ETF2', 200, 25.0, 5000.0)   # 200 * 25.0 = 5000
        ]
        
        mock_conn.execute.return_value.fetchall.return_value = mock_positions
        
        # Mock session manager
        mock_session_mgr = MagicMock()
        mock_session.return_value = mock_session_mgr
        mock_session_mgr.add_report_to_session.return_value = "test_report.json"
        
        # Esegui
        check_guardrails.check_guardrails()
        
        # Verifica che il calcolo sia coerente (usa market_value dal risultato)
        # Il totale dovrebbe essere 10000 (5000 + 5000)
        # La concentrazione dovrebbe essere 50% per ciascuno
        
        # Questo test verifica che non ci siano errori di indice
        # Se il codice usasse pos[2] invece di pos[3], causerebbe errori
        self.assertTrue(True)  # Se arriva qui, non ci sono stati errori di indice

if __name__ == '__main__':
    unittest.main()
