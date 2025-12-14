import unittest
import pandas as pd
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import patch

# Configure logging to capture output
logging.basicConfig(level=logging.INFO)

# Import module under test
# We might need to handle sys.path if running as script
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src")))

from mie_lib.analytics.tsmom.data_loader import load_ohlc_daily, load_all_tickers_ohlc, DataNotFoundError

class TestTSMOMDataLoader(unittest.TestCase):
    
    def setUp(self):
        # Create a temp directory for raw data
        self.test_dir = tempfile.mkdtemp()
        self.mock_raw_dir = Path(self.test_dir)
        
        # Patch RAW_DIR in the module
        self.patcher = patch("mie_lib.analytics.tsmom.data_loader.RAW_DIR", self.mock_raw_dir)
        self.patcher.start()
        
    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_load_ohlc_daily_success(self):
        # Create a dummy parquet file
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "close": [100.0, 101.0, 102.0],
            "adj_close": [100.0, 101.0, 102.5] # Diff at end
        })
        ticker = "TEST_SUCCESS"
        path = self.mock_raw_dir / f"{ticker}.parquet"
        df.to_parquet(path)
        
        # Load
        loaded_df = load_ohlc_daily(ticker)
        
        # Verify
        self.assertIsInstance(loaded_df.index, pd.DatetimeIndex)
        self.assertTrue(loaded_df.index.is_monotonic_increasing)
        self.assertEqual(len(loaded_df), 3)
        self.assertIn("price", loaded_df.columns)
        self.assertEqual(loaded_df.iloc[-1]["price"], 102.5) # Should prefer adj_close

    def test_load_ohlc_daily_missing(self):
        with self.assertRaises(DataNotFoundError):
            load_ohlc_daily("MISSING_TICKER")

    def test_load_all_tickers_ohlc_parallel(self):
        # Create multiple tickers
        tickers = ["T1", "T2", "TX"] # TX missing
        
        # T1
        pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01"]), "close": [10.0]
        }).to_parquet(self.mock_raw_dir / "T1.parquet")
        
        # T2
        pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01"]), "close": [20.0]
        }).to_parquet(self.mock_raw_dir / "T2.parquet")
        
        results = load_all_tickers_ohlc(tickers, max_workers=2)
        
        self.assertIn("T1", results)
        self.assertIn("T2", results)
        self.assertNotIn("TX", results)
        self.assertEqual(results["T1"].iloc[0]["price"], 10.0)

if __name__ == '__main__':
    unittest.main()
