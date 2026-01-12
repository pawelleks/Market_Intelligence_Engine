#!/usr/bin/env python3
"""
Leading Indicators Index (LEI) Generator

Fetches T10Y2Y, PERMIT, and SP500 from FRED.
Normalizes using a 5-year rolling Z-score.
Creates a composite LEI index and a smoothed signal line.

Output: data/processed/lei_model.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from fredapi import Fred
import os
from dotenv import load_dotenv
import ssl
import certifi
import urllib.request

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

# Constants
START_YEAR = "1970-01-01"
ROLLING_WINDOW_YR = 10
COMPONENT_SMOOTH_MONTHS = 6
SIGNAL_12M_MONTHS = 12
SIGNAL_18M_MONTHS = 18
SIGNAL_24M_MONTHS = 24

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "macro" / "fred"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_FILE = PROCESSED_DATA_DIR / "lei_model.parquet"

def rolling_z_score(series, window_years=10, min_periods=12):
    """Calculate rolling Z-score with expanding window fallback for early data."""
    window = window_years * 12
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    return (series - rolling_mean) / rolling_std

def main():
    LOG.info("Loading RAW macro series for LEI...")
    
    # Components Map
    # Sid -> Internal Name
    fred_series = {
        'T10Y2Y': 'yield_2y',
        'T10Y3M': 'yield_3m',
        'PERMIT': 'housing',
        'NEWORDER': 'orders'
    }
    
    dfs = []
    for sid, name in fred_series.items():
        p = RAW_DIR / f"{sid}.parquet"
        if not p.exists():
            LOG.error(f"Missing data for {sid} at {p}")
            return
        df = pd.read_parquet(p)
        df.set_index('date', inplace=True)
        # Resample to monthly (MS)
        df = df.resample('MS').last().rename(columns={'value': name})
        dfs.append(df)

    # Local S&P 500 series (^GSPC)
    sp500_path = BASE_DIR / "data" / "raw" / "^GSPC.parquet"
    if sp500_path.exists():
        LOG.info(f"Using local SP500 data from {sp500_path}")
        df_sp = pd.read_parquet(sp500_path)
        df_sp.set_index('date', inplace=True)
        df_sp = df_sp.resample('MS').last().rename(columns={'close': 'sp500'})
        dfs.append(df_sp[['sp500']])
    else:
        LOG.error(f"Missing local SP500 data at {sp500_path}")
        return

    # Join and align
    data = dfs[0]
    for df in dfs[1:]:
        data = data.join(df, how='outer')
    
    data = data.sort_index().ffill()

    LOG.info("Applying transformations (YoY)...")
    data['housing_yoy'] = data['housing'].pct_change(periods=12)
    data['orders_yoy'] = data['orders'].pct_change(periods=12)
    data['sp500_yoy'] = data['sp500'].pct_change(periods=12)

    LOG.info("Calculating component Z-scores (Mixed Rolling Windows)...")
    # We use 60M (5Y) for components as found in calibration to be more responsive
    z_map = {
        'yield_2y': 'z_yield_2y',
        'yield_3m': 'z_yield_3m',
        'housing_yoy': 'z_housing',
        'orders_yoy': 'z_orders',
        'sp500_yoy': 'z_sp500'
    }
    for col, z_col in z_map.items():
        # Using 5Y rolling window but allowing expanding start (min 12 months)
        data[z_col] = rolling_z_score(data[col], window_years=5, min_periods=12)

    LOG.info(f"Applying {COMPONENT_SMOOTH_MONTHS}-month smoothing and 18M Yield Lag...")
    for z_col in z_map.values():
        data[f'{z_col}_smooth'] = data[z_col].rolling(window=COMPONENT_SMOOTH_MONTHS).mean()

    # Apply 18-Month Lag to Yields specifically (Calibrated to hit Late 2024 zero-cross)
    # Only if data exists (shift handles NaNs naturally)
    data['z_yield_2y_smooth'] = data['z_yield_2y_smooth'].shift(18)
    data['z_yield_3m_smooth'] = data['z_yield_3m_smooth'].shift(18)

    LOG.info("Calculating LEI Composite with Dynamic Weighting...")
    # Target weights: T10Y2Y: 25%, T10Y3M: 25%, Housing: 25%, Orders: 15%, SP500: 10%
    weights = {
        'z_yield_2y_smooth': 0.25,
        'z_yield_3m_smooth': 0.25,
        'z_housing_smooth': 0.25,
        'z_orders_smooth': 0.15,
        'z_sp500_smooth': 0.10
    }
    
    # Calculate weighted sum handling NaNs
    # For each row, calculate the sum of available (weight * value) and divide by the sum of weights of available components
    def calculate_weighted_composite(row):
        available_val_weights = []
        sum_weights = 0
        for col, w in weights.items():
            val = row[col]
            if not pd.isna(val):
                available_val_weights.append(val * w)
                sum_weights += w
        
        if sum_weights == 0:
            return np.nan
        return sum(available_val_weights) / sum_weights

    data['composite_raw'] = data.apply(calculate_weighted_composite, axis=1)

    LOG.info("Applying Post-Composite Normalization and Signal Generation...")
    # Post-Normalization (10-Year Rolling) - expanding fallback to ensure early start
    # Amplitude Scaling: 2.0x to hit the +/- 3 target range as requested
    data['lei_composite'] = rolling_z_score(data['composite_raw'], window_years=10, min_periods=12) * 2.0

    LOG.info("Generating Signal Lines (12M, 18M, and 24M)...")
    data['signal_12m'] = data['lei_composite'].rolling(window=SIGNAL_12M_MONTHS).mean()
    data['signal_18m'] = data['lei_composite'].rolling(window=SIGNAL_18M_MONTHS).mean()
    data['signal_24m'] = data['lei_composite'].rolling(window=SIGNAL_24M_MONTHS).mean()
    
    # Old field aliasing for backward compatibility
    data['signal_line'] = data['signal_12m'] 

    # Filter for data from 1980 onwards as requested
    data = data[data.index >= '1980-01-01']
    
    # Clean up NaNs from smoothing
    data = data.dropna(subset=['lei_composite', 'signal_12m'])
    
    LOG.info(f"Saving LEI model to {OUTPUT_FILE}...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.to_parquet(OUTPUT_FILE)
    
    print("\n" + "="*50)
    print("LEI Model Indicators: Last 5 Months")
    print("="*50)
    print(data[['lei_composite', 'signal_12m', 'signal_18m', 'signal_24m']].tail(5))
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
