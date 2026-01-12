#!/usr/bin/env python3
"""
Create S&P 500 Returns Dataset

Processes existing S&P 500 price data and calculates forward returns
and drawdown metrics for market performance analysis.

Output: data/outcomes/sp500_returns.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outcomes"
OUTPUT_FILE = OUTPUT_DIR / "sp500_returns.parquet"


def calculate_forward_returns(df, periods_dict):
    """
    Calculate forward returns for specified periods.
    
    Args:
        df: DataFrame with 'date' and 'close' columns
        periods_dict: Dict mapping column name to number of trading days
                     (e.g., {'return_6m': 126, 'return_12m': 252})
    
    Returns:
        DataFrame with forward return columns added
    """
    for col_name, days in periods_dict.items():
        # Shift close prices backward to get future prices
        future_price = df['close'].shift(-days)
        # Calculate percentage return
        df[col_name] = ((future_price / df['close']) - 1) * 100
    
    return df


def calculate_drawdown(df, window=252):
    """
    Calculate drawdown from rolling peak.
    
    Args:
        df: DataFrame with 'close' column
        window: Rolling window for peak calculation (252 = ~1 year)
    
    Returns:
        DataFrame with 'rolling_peak' and 'drawdown_pct' columns
    """
    # Calculate rolling maximum (peak)
    df['rolling_peak'] = df['close'].rolling(window=window, min_periods=1).max()
    
    # Calculate drawdown percentage
    df['drawdown_pct'] = ((df['close'] / df['rolling_peak']) - 1) * 100
    
    return df


def main():
    print("Creating S&P 500 Returns Dataset")
    print("=" * 60)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load S&P 500 data
    print("\n1. Loading S&P 500 data...")
    sp500_file = RAW_DATA_DIR / "^GSPC.parquet"
    
    if not sp500_file.exists():
        raise FileNotFoundError(f"S&P 500 data not found at {sp500_file}")
    
    df = pd.read_parquet(sp500_file)
    
    # Ensure date column and sort
    if 'date' not in df.columns and df.index.name == 'date':
        df = df.reset_index()
    
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"   Loaded {len(df)} daily observations")
    print(f"   Period: {df['date'].min()} to {df['date'].max()}")
    
    # Keep only necessary columns
    df = df[['date', 'close']].copy()
    
    # Calculate forward returns
    print("\n2. Calculating forward returns...")
    periods = {
        'return_6m': 126,   # ~6 months (21 trading days/month * 6)
        'return_12m': 252,  # ~12 months  
        'return_24m': 504   # ~24 months
    }
    
    df = calculate_forward_returns(df, periods)
    
    for col, days in periods.items():
        valid_count = df[col].notna().sum()
        print(f"   {col}: {valid_count} valid observations ({days} days)")
    
    # Calculate drawdown
    print("\n3. Calculating drawdown from peak...")
    df = calculate_drawdown(df, window=252)
    
    max_dd = df['drawdown_pct'].min()
    avg_dd = df['drawdown_pct'].mean()
    print(f"   Max drawdown: {max_dd:.2f}%")
    print(f"   Avg drawdown: {avg_dd:.2f}%")
    
    # Save to parquet
    print(f"\n4. Saving to {OUTPUT_FILE}...")
    df.to_parquet(OUTPUT_FILE, index=False)
    
    print("\n" + "=" * 60)
    print("✅ S&P 500 Returns Dataset created successfully!")
    print(f"   Output: {OUTPUT_FILE}")
    print(f"   Observations: {len(df)}")
    print(f"   Period: {df['date'].min().year} - {df['date'].max().year}")
    print(f"   Columns: {list(df.columns)}")
    
    return df


if __name__ == "__main__":
    df = main()
