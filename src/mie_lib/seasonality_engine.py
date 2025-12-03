import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Define paths
RAW_DIR = Path("data/raw")
SEASONALITY_BASE_DIR = Path("data/seasonality/base")

def ensure_seasonality_dir():
    """Ensures the output directory exists."""
    SEASONALITY_BASE_DIR.mkdir(parents=True, exist_ok=True)

def generate_seasonality_base(ticker: str):
    """
    Generates the seasonality base file for a given ticker.
    Enriches raw OHLC data with:
    - Log Returns (lr) and Simple Returns (r)
    - Calendar metadata (year, month, day)
    - Trading Day of Year (tdoy) for curve alignment
    """
    ensure_seasonality_dir()
    ticker = ticker.upper()
    
    raw_path = RAW_DIR / f"{ticker}.parquet"
    if not raw_path.exists():
        print(f"❌ Raw data not found for {ticker}. Run 'rebuild-raw' first.")
        return

    # 1. Load Raw Data
    df = pd.read_parquet(raw_path)
    
    # Ensure date is datetime and sorted
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    else:
        # If date is the index, reset it
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["date"])
    
    df = df.sort_values("date").reset_index(drop=True)

    # 2. Normalize Price Columns
    # We need 'close' for returns. Handle 'Close', 'Adj Close', 'adj_close'
    cols_map = {c: c.lower().replace(' ', '_') for c in df.columns}
    df = df.rename(columns=cols_map)
    
    price_col = 'adj_close' if 'adj_close' in df.columns else 'close'
    if price_col not in df.columns:
         print(f"❌ Price column missing for {ticker}.")
         return

    # 3. Calculate Returns
    # Simple Return (r)
    df['r'] = df[price_col].pct_change()
    
    # Log Return (lr) = ln(1 + r)
    # Use numpy for vectorized log calculation
    df['lr'] = np.log(df[price_col] / df[price_col].shift(1))
    
    # 4. Add Calendar Metadata
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day
    
    # 5. Calculate Trading Day of Year (TDOY)
    # TDOY is the cumulative count of trading days within that specific year
    df['tdoy'] = df.groupby('year').cumcount() + 1
    
    # 6. Save to Parquet
    out_path = SEASONALITY_BASE_DIR / f"{ticker}.parquet"
    df.to_parquet(out_path)
    print(f"✅ Seasonality base data generated: {out_path}")
