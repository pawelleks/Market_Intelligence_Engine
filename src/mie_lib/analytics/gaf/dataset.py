import pandas as pd
import numpy as np
from typing import Tuple, List
from mie_lib.data_ingest.yfinance_loader import fetch_full_history

def fetch_and_prepare_data(ticker: str, window_size: int = 20) -> pd.DataFrame:
    """Fetch history and ensure sufficient data."""
    meta = fetch_full_history(ticker)
    df = pd.read_parquet(meta['parquet'])
    
    # Ensure sorted by date
    df = df.sort_values('date').reset_index(drop=True)
    return df

def create_windows_and_labels(df: pd.DataFrame, window_size: int = 20) -> Tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """
    Create sliding windows of closing prices and binary labels.
    Label 1 = Next Day Close > Current Day Close (UP)
    Label 0 = Next Day Close <= Current Day Close (DOWN)
    
    Returns:
        X: (num_samples, window_size)
        y: (num_samples,)
        dates: (num_samples,) The date of the LAST day in the window (T)
    """
    prices = df['adj_close' if 'adj_close' in df.columns else 'close'].values
    dates = df['date'].values
    
    X = []
    y = []
    valid_dates = []
    
    # Iterate through array
    # We need window_size past days + 1 future day for label
    # Range: start from window_size to end-1
    # Example: window=3. [p0, p1, p2, p3]. Window=[p0,p1,p2]. Label based on p3 vs p2.
    
    for i in range(window_size, len(prices)):
        window = prices[i-window_size : i] # Indices [i-w ... i-1]
        current_close = window[-1]
        next_close = prices[i] # This is the future target relative to the window
        
        # Normalize Window?
        # GAF usually handles scaling, but min-max scaling per window is often good practice
        # pyts GAF scales [-1, 1] internally usually, but let's feed raw for now as encoder handles it.
        
        # Label Construction
        label = 1 if next_close > current_close else 0
        
        X.append(window)
        y.append(label)
        valid_dates.append(dates[i-1]) # Date of the last known price in the window
        
    return np.array(X), np.array(y), pd.to_datetime(valid_dates)
