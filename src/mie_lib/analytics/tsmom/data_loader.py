"""
Data Loading Layer for TSMOM Module.
Handles ingestion of daily OHLC data from Parquet files.
"""
import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from mie_lib.utils.paths import RAW_DIR

LOG = logging.getLogger(__name__)

class DataNotFoundError(Exception):
    """Raised when data for a ticker cannot be found."""
    pass

def load_ohlc_daily(ticker: str) -> pd.DataFrame:
    """
    Loads daily OHLC data for a specific ticker.
    
    Args:
        ticker: Ticker symbol (e.g., 'SPY').
        
    Returns:
        pd.DataFrame: DataFrame with DatetimeIndex, sorted ascending.
        
    Raises:
        DataNotFoundError: If the parquet file does not exist.
    """
    path = RAW_DIR / f"{ticker}.parquet"
    
    if not path.exists():
        # Fallback to .csv if parquet missing? 
        # User defined requirements: "Read data/ohlc/{ticker}.parquet (or equivalent path from config)"
        # We adhere to RAW_DIR for consistency.
        raise DataNotFoundError(f"No parquet file found for {ticker} at {path}")
        
    try:
        df = pd.read_parquet(path)
        
        # Normalize columns
        df.columns = [c.lower() for c in df.columns]
        
        # Ensure Date Index
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            
        if not isinstance(df.index, pd.DatetimeIndex):
             # Try to convert index if strictly needed, or raise
             df.index = pd.to_datetime(df.index)

        df = df.sort_index(ascending=True)
        
        # Standardize 'close' column availability (handle adj_close vs close preference?)
        # For TSMOM, we prefer Adjusted Close usually.
        if "adj_close" in df.columns:
            df["price"] = df["adj_close"]
        elif "close" in df.columns:
            df["price"] = df["close"]
        else:
            # If no price column, might strictly be invalid
            pass 
            
        return df
        
    except Exception as e:
        raise RuntimeError(f"Failed to read/parse data for {ticker}: {e}")

def load_all_tickers_ohlc(tickers: List[str], max_workers: int = 4) -> Dict[str, pd.DataFrame]:
    """
    Loads OHLC data for multiple tickers in parallel.
    
    Args:
        tickers: List of ticker symbols.
        max_workers: Number of threads for parallel execution.
        
    Returns:
        Dict[str, pd.DataFrame]: Dictionary mapping ticker -> DataFrame.
                                 Failed loads are omitted from the dict (logged as warning).
    """
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(load_ohlc_daily, t): t for t in tickers}
        
        for future in as_completed(future_map):
            t = future_map[future]
            try:
                df = future.result()
                if not df.empty:
                    results[t] = df
            except DataNotFoundError:
                LOG.warning(f"Data not found for {t}")
            except Exception as e:
                LOG.error(f"Error loading {t}: {e}")
                
    return results
