#!/usr/bin/env python3
"""
Coincident Indicators Index (COI) Generator - NBER-Aligned Model

Fetches PAYEMS, INDPRO, W875RX1, and CMRMTSPL from FRED.
Applies 12-Month SMA smoothing to YoY values before Z-scoring.
Creates a composite COI index and a 3-month signal line.

This configuration matches the TradingView COI fingerprint:
- 2008 Financial Crisis dip is DEEPER than 2020 COVID dip.

Output: data/processed/coi_model.parquet
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
from datetime import datetime

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

# Constants
START_YEAR = "1990-01-01"  # Data available for RRSFS starting 1992
ROLLING_WINDOW_YR = 15     # 15-year window to normalize by pre-COVID volatility
SMA_SMOOTH_MONTHS = 24     # Signal line (Lazy 24M SMA)
COMPONENT_SMOOTH_MONTHS = 24  # Component-level smoothing (Model D winner)

# Series IDs
INDUSTRIAL_PRODUCTION = "INDPRO"
REAL_RETAIL_SALES = "RRSFS"  # Real Retail and Food Services Sales

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
RAW_MACRO_DIR = BASE_DIR / "data" / "raw" / "macro" / "fred"
OUTPUT_FILE = PROCESSED_DATA_DIR / "coi_model.parquet"

def load_cached_series(series_id):
    """Load FRED series from cached parquet file."""
    file_path = RAW_MACRO_DIR / f"{series_id}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Cached series {series_id} not found at {file_path}. Please run the Economic Pipeline's FRED data fetch step first.")
    df = pd.read_parquet(file_path)
    
    # Ensure 'date' column becomes the index
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    
    # Extract the value column as Series
    if 'value' in df.columns:
        s = df['value']
    elif df.shape[1] == 1:
        s = df.iloc[:, 0]
    else:
        raise ValueError(f"Unexpected DataFrame structure for {series_id}")
    
    # Return as Series (COI script expects Series for processing)
    return s

def fetch_macro_data():
    """Load macro series from cache (Model D components: IndPro + Retail)."""
    LOG.info("Loading macro data for Model D COI (IndPro + Retail) from cache...")
    
    try:
        series_ids = {
            'indpro': INDUSTRIAL_PRODUCTION,
            'retail': REAL_RETAIL_SALES
        }
        
        dfs = []
        for name, sid in series_ids.items():
            LOG.info(f"Loading {sid} from cache...")
            s = load_cached_series(sid)
            # Use to_frame to preserve index and rename column correctly
            df = s.to_frame(name=name)
            dfs.append(df)
            
        join_df = dfs[0]
        for df in dfs[1:]:
            join_df = join_df.join(df, how='outer')
            
        return join_df.resample('MS').last()
    except Exception as e:
        LOG.error(f"Error loading data from cache: {e}")
        raise

def calculate_coi(df):
    """
    Apply transformations, smoothing, Z-scores, and composite calculation.
    Uses Model D specs: 24M smooth, 15Y Z-score.
    """
    LOG.info("Calculating Model D COI components and Z-scores...")
    
    # 1. Transformations: YoY Change
    df['indpro_yoy_raw'] = df['indpro'].pct_change(periods=12)
    df['retail_yoy_raw'] = df['retail'].pct_change(periods=12)
    
    # 2. Smoothing Components: 24-Month SMA (Crushes 2020 spike)
    LOG.info(f"Applying {COMPONENT_SMOOTH_MONTHS}-month smoothing to components...")
    df['indpro_yoy'] = df['indpro_yoy_raw'].rolling(window=COMPONENT_SMOOTH_MONTHS).mean()
    df['retail_yoy'] = df['retail_yoy_raw'].rolling(window=COMPONENT_SMOOTH_MONTHS).mean()

    # Drop rows until smoothed YoY is available
    df = df.dropna(subset=['indpro_yoy', 'retail_yoy'])
    
    # 3. Rolling Z-Score (Rolling 15-Year)
    def rolling_z_score(series, window_years=15):
        window = window_years * 12
        rolling_mean = series.rolling(window=window, min_periods=1).mean()
        rolling_std = series.rolling(window=window, min_periods=1).std()
        return (series - rolling_mean) / rolling_std

    df['z_indpro'] = rolling_z_score(df['indpro_yoy'], ROLLING_WINDOW_YR)
    df['z_retail'] = rolling_z_score(df['retail_yoy'], ROLLING_WINDOW_YR)
    
    # 4. Composite Index
    df['coi_composite'] = (df['z_indpro'] + df['z_retail']) / 2
    
    # 5. Signal Line (Lazy 24-Month SMA)
    LOG.info(f"Applying lazy {SMA_SMOOTH_MONTHS}-month smoothing to signal line...")
    df['signal_line'] = df['coi_composite'].rolling(window=SMA_SMOOTH_MONTHS).mean()
    
    return df.dropna(subset=['signal_line'])

def validate_fingerprint(df):
    """
    Validate that 2008 crisis is deeper than 2020 COVID.
    Expected for Model D: ~4:1 Ratio.
    """
    LOG.info("\n" + "="*60)
    LOG.info("VALIDATION: Model D Fingerprint Check")
    LOG.info("="*60)
    
    crisis_2008 = (df.index >= '2008-01-01') & (df.index <= '2009-12-31')
    crisis_2020 = (df.index >= '2020-01-01') & (df.index <= '2020-12-31')
    
    min_2008 = df.loc[crisis_2008, 'coi_composite'].min()
    min_2020 = df.loc[crisis_2020, 'coi_composite'].min()
    
    ratio = abs(min_2008 / min_2020) if min_2020 != 0 else 0
    LOG.info(f"2008 Crisis Minimum: {min_2008:.4f}")
    LOG.info(f"2020 COVID Minimum:  {min_2020:.4f}")
    LOG.info(f"Ratio (2008/2020):   {ratio:.2f}")
    
    if ratio > 2.0:
        LOG.info(f"✓ FINGERPRINT MATCH: 2008 is overwhelmingly deeper.")
    else:
        LOG.warning(f"✗ FINGERPRINT WEAK: Ratio is only {ratio:.2f}")
    LOG.info("="*60 + "\n")

def save_results(df):
    """
    Save to Parquet.
    """
    LOG.info(f"Saving Model D COI to {OUTPUT_FILE}...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Final column selection
    cols = ['coi_composite', 'signal_line', 'indpro_yoy', 'retail_yoy']
    df[cols].to_parquet(OUTPUT_FILE)
    LOG.info("COI model saved successfully.")
    
    post_ts = datetime.fromtimestamp(OUTPUT_FILE.stat().st_mtime)
    LOG.info(f"File timestamp AFTER save:  {post_ts.strftime('%Y-%m-%d %H:%M:%S')}")
    LOG.info("COI model saved successfully.")

def main():
    try:
        df = fetch_macro_data()
        df = calculate_coi(df)
        
        print("\n" + "="*50)
        print("Coincident Indicators Index (COI): Last 5 Months")
        print("="*50)
        print(df[['coi_composite', 'signal_line']].tail(5))
        print("="*50 + "\n")
        
        # Validate fingerprint
        validate_fingerprint(df)
        
        save_results(df)
        LOG.info("COI Index generation complete!")
        
    except Exception as e:
        LOG.error(f"Failed to generate COI Index: {e}")
        exit(1)

if __name__ == "__main__":
    main()
