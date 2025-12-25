import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from mie_lib.analytics.psar import calculate_psar, calculate_and_save_psar

def test_calculate_psar_uptrend():
    # Construct a simple uptrend sequence
    # Day 0: Close < Open (Down) -> Initial Trend Down (assumed)
    # Then strong upward movement
    high = np.array([10, 11, 12, 13, 14, 15], dtype=float)
    low  = np.array([ 9, 10, 11, 12, 13, 14], dtype=float)
    close= np.array([ 9.5, 10.5, 11.5, 12.5, 13.5, 14.5], dtype=float)
    
    # trend logic in code: 
    # if close[0] >= close[1] -> Down. Here 9.5 < 10.5 -> Up? 
    # logic: if close[0] >= close[1]: down else up.
    # 9.5 < 10.5 -> Up.
    
    df_res = calculate_psar(high, low, close)
    
    assert len(df_res) == 6
    assert "psar" in df_res.columns
    assert "psar_trend" in df_res.columns
    
    # Check that trend eventually is 1 (Bullish) or psar < close
    # At index 5:
    assert df_res["psar"].iloc[5] < close[5]
    assert df_res["psar_trend"].iloc[5] == 1


def test_calculate_psar_reversal():
    """Test that PSAR flips when price crosses it."""
    # Uptrend then crash
    # 0,1,2 up
    # 3,4 crash
    high = np.array([10, 12, 14, 13, 10], dtype=float)
    low  = np.array([ 8, 10, 12, 10, 8], dtype=float)
    close= np.array([ 9, 11, 13, 11, 8], dtype=float)
    
    # 0 vs 1: 9 < 11 -> Up initially
    df_res = calculate_psar(high, low, close)
    
    # Initially up
    assert df_res["psar_trend"].iloc[1] == 1 
    
    # Should reverse to -1 at some point
    # At index 4 (Close 8), if prev PSAR was higher, it flips
    last_trend = df_res["psar_trend"].iloc[-1]
    assert last_trend == -1 or df_res["psar"].iloc[-1] > close[-1]


@patch("mie_lib.analytics.psar.read_tickers")
@patch("pandas.read_parquet")
@patch("pathlib.Path.exists")
@patch("pandas.DataFrame.to_parquet")
def test_calculate_and_save_psar(mock_to_parquet, mock_exists, mock_read_parquet, mock_read_tickers, tmp_path):
    # Setup mocks
    mock_read_tickers.return_value = ["AAPL", "GOOG"]
    mock_exists.return_value = True
    
    # Create valid OHLC data
    dates = pd.date_range("2023-01-01", periods=10)
    data = {
        "date": dates,
        "high": np.linspace(100, 110, 10),
        "low": np.linspace(90, 100, 10),
        "close": np.linspace(95, 105, 10),
        "open": np.linspace(95, 105, 10),
        "volume": [1000]*10
    }
    df = pd.DataFrame(data)
    
    mock_read_parquet.return_value = df
    
    # Run
    calculate_and_save_psar()
    
    # Verify save called
    assert mock_to_parquet.called
    
    # Check valid content passed to save
    # args[0] of the call # call_args[0][0] ?
    # call args: (path, index=False)
    # Actually to_parquet is called on the dataframe instance
    # So we check mock_to_parquet explicitly? 
    # Actually I mocked DataFrame.to_parquet directly which might be tricky if it's an instance method.
    # Better to inspect what calculate_and_save_psar produced if possible, or just trust the mock call count.
    
    # Wait, patching DataFrame.to_parquet is patching the class method. 
    # The actual call is `out_df.to_parquet(...)`. `out_df` is a new DF created inside the function.
    # So `pd.DataFrame.to_parquet` mock should capture it.
    
    assert mock_to_parquet.call_count == 1
    
    # Argument verification
    # Getting the DF that called it is harder with `patch` on class method unless we use autospec=True or similar.
    # But we can verify arguments.
    args, kwargs = mock_to_parquet.call_args
    # args[0] is the path
    assert "psar_daily.parquet" in str(args[0])

