import unittest
import pandas as pd
import numpy as np
import logging
from unittest.mock import patch, MagicMock
from datetime import date

# Import module under test
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src")))

from mie_lib.analytics.tsmom.engine import run_tsmom_daily_update

class TestTSMOMRunner(unittest.TestCase):
    
    def setUp(self):
        # Create Dummy Data
        # We need enough history for lookback (252) + some changes
        # Let's use lookback=5 for testing to keep data small
        self.lookback = 5
        
        dates = pd.date_range("2025-01-01", periods=20, freq="B")
        prices = [100] * 20
        # Create a trend:
        # 0-5: 100
        # 6-10: 110 (+10% -> Signal +1)
        # 11-15: 90 (-10% vs 100/110 -> Signal -1)
        # 16-19: 100 (+10% vs 90 -> Signal +1)
        
        # Adjust manually
        # ret = price / price_lag - 1
        # if lookback=5
        # date[5] vs date[0]: ?
        
        # Let's simplify:
        # index 0-9: 100
        # index 10-14: 110 (ret = 1.1 > 0 -> +1)
        # index 15-19: 90 (ret = 90/110 < 0 -> -1)
        
        prices = ([100.0] * 10) + ([110.0] * 5) + ([90.0] * 5)
        
        self.df = pd.DataFrame({
            "price": prices,
            # "close": prices, # engine uses 'price' (standardized by loader)
            "date": dates
        }).set_index("date")
        
        self.tickers = ["TEST_TICKER"]
        self.ohlc_map = {"TEST_TICKER": self.df}

    @patch("mie_lib.analytics.tsmom.engine.load_all_tickers_ohlc")
    @patch("mie_lib.analytics.tsmom.engine.save_current_snapshot")
    @patch("mie_lib.analytics.tsmom.engine.append_signal_history")
    def test_run_daily_mode_no_signal_today(self, mock_append, mock_save, mock_load):
        # Setup
        mock_load.return_value = self.ohlc_map
        
        # In our data, last day (idx 19) is 90. Lag 5 (idx 14) is 110.
        # Ret = 90/110 - 1 < 0. Signal -1.
        # Prev day (idx 18) is 90. Lag 5 (idx 13) is 110.
        # Ret < 0. Signal -1.
        # So NO CHANGE on last day.
        
        summary = run_tsmom_daily_update(lookback_days=self.lookback, tickers=self.tickers, backfill=False)
        
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["signals_generated"], 0)
        
        # Verify snapshot saved
        self.assertTrue(mock_save.called)
        # Verify signal history NOT called (no signal today)
        self.assertFalse(mock_append.called)

    @patch("mie_lib.analytics.tsmom.engine.load_all_tickers_ohlc")
    @patch("mie_lib.analytics.tsmom.engine.save_current_snapshot")
    @patch("mie_lib.analytics.tsmom.engine.append_signal_history")
    def test_run_backfill_mode(self, mock_append, mock_save, mock_load):
        # Setup
        mock_load.return_value = self.ohlc_map
        
        summary = run_tsmom_daily_update(lookback_days=self.lookback, tickers=self.tickers, backfill=True)
        
        # We expect signals:
        # 1. First time ret becomes calculable and != 0 (idx 10: 110 vs 100 -> +1)
        # 2. Flip from +1 to -1 (idx 15: 90 vs 110 -> -1)
        # Note: idx 0-4 are NaN ret. idx 5-9 are 100 vs 100 = 0 ret (dir 0).
        # idx 10: 110/100 - 1 > 0 -> +1. Prev was 0. -> Change! (Signal 1)
        # idx 11-14: +1. No change.
        # idx 15: 90/110 - 1 < 0 -> -1. Prev was +1. -> Change! (Signal 2)
        # idx 16-19: -1. No change.
        
        # Total expected signals: 2
        
        self.assertEqual(summary["signals_generated"], 2)
        
        # Check append calls
        self.assertTrue(mock_append.called)
        args, _ = mock_append.call_args
        df_sig = args[0]
        self.assertEqual(len(df_sig), 2)
        self.assertEqual(df_sig.iloc[0]["signal"], "BUY") # 0 -> +1 (detected as BUY in logic if > 0)
        self.assertEqual(df_sig.iloc[1]["signal"], "SELL") # +1 -> -1

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
