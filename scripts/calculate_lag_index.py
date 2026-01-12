#!/usr/bin/env python3
"""
Lagging Economic Indicator (LAG) - Confirmation Engine

Calculates a composite index of "sticky" physical economy variables:
1. CPI Services (Less Rent/Shelter)
2. Unemployment Rate (Inverted)
3. Unit Labor Costs (Manufacturing)
4. Commercial & Industrial Loans

Output: data/processed/lag_model.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from fredapi import Fred
import os
import sys
from dotenv import load_dotenv
import ssl
import certifi
import urllib.request
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mie_lib.utils.paths import DATA_DIR

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("lag_index")

# Constants
START_YEAR = "1990-01-01"
ROLLING_WINDOW_YR = 5
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = PROCESSED_DATA_DIR / "lag_model.parquet"

# SSL Workaround
try:
    context = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
    urllib.request.install_opener(opener)
except Exception as e:
    LOG.warning(f"SSL context setup failed: {e}")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_MACRO_DIR = BASE_DIR / "data" / "raw" / "macro" / "fred"

# FRED API
FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY not found in environment variables")

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
    
    # Return as DataFrame with proper DatetimeIndex
    result = pd.DataFrame({series_id: s})
    result.index = pd.to_datetime(result.index)
    return result

def rolling_z_score(series, window_years=5):
    window = window_years * 12
    return (series - series.rolling(window=window, min_periods=1).mean()) / series.rolling(window=window, min_periods=1).std()

def calculate_lag_index():
    LOG.info("Starting LAG Index calculation...")
    
    # 1. Load Cached Data (instead of fetching from FRED API)
    cpi_serv = load_cached_series("CUSR0000SASL2RS") # CPI Services Less Rent
    unrate = load_cached_series("UNRATE")           # Unemployment Rate
    ulc = load_cached_series("ULCMFG")             # Unit Labor Costs (Manufacturing)
    loans = load_cached_series("BUSLOANS")         # Commercial & Industrial Loans
    
    # 2. Alignment & Resampling
    # join monthly and quarterly data
    df = cpi_serv.join([unrate, ulc, loans], how='outer').resample('MS').last()
    
    # Interpolate quarterly ULCMFG
    df['ULCMFG'] = df['ULCMFG'].interpolate(method='linear')
    
    # 3. Transformations (The "Inertia" Filter)
    # Use YoY (12M) to capture deep structural trends, not short-term noise.
    df['cpi_serv_yoy'] = df['CUSR0000SASL2RS'].pct_change(12)
    df['unrate_inverted'] = -df['UNRATE'] # Level, not growth. High level = cycle top.
    df['ulc_yoy'] = df['ULCMFG'].pct_change(12)
    df['loans_yoy'] = df['BUSLOANS'].pct_change(12)
    
    # 4. Normalization (5-Year Rolling Z-Score)
    df['z_cpi'] = rolling_z_score(df['cpi_serv_yoy'], ROLLING_WINDOW_YR)
    df['z_unrate'] = rolling_z_score(df['unrate_inverted'], ROLLING_WINDOW_YR)
    df['z_ulc'] = rolling_z_score(df['ulc_yoy'], ROLLING_WINDOW_YR)
    df['z_loans'] = rolling_z_score(df['loans_yoy'], ROLLING_WINDOW_YR)
    
    # 5. Composite Index (Equal Weight)
    df['lag_composite_raw'] = df[['z_cpi', 'z_unrate', 'z_ulc', 'z_loans']].mean(axis=1)
    
    # 6. Heavy Smoothing (6-Month SMA)
    # The Lagging Index represents "Inertia" - it must turn slowly.
    df['lag_composite'] = df['lag_composite_raw'].rolling(6).mean()
    
    # 7. Signal Line (12-Month SMA for Better Confirmation)
    # Lagging indicators need longer smoothing for reliable trend confirmation
    df['signal_line'] = df['lag_composite'].rolling(12).mean()
    
    return df

def validate_fed_trap(df):
    """
    Check if the LAG index peaked in Q3 2008 (well after the cycle turned).
    Recession started Dec 2007. LEI peaks usually 12 months before that.
    LAG should peak in 2008.
    """
    period_2008 = df.loc['2007-01-01':'2009-01-01']
    if period_2008.empty:
        LOG.warning("No 2008 data for Fed Trap validation.")
        return
    
    peak_date = period_2008['lag_composite'].idxmax()
    peak_val = period_2008['lag_composite'].max()
    
    LOG.info(f"FED TRAP VALIDATION: 2008 Peak detected on {peak_date.date()} (Value: {peak_val:.4f})")
    
    # Q3 2008 is July, August, September
    if peak_date.month in [7, 8, 9] and peak_date.year == 2008:
        LOG.info("✅ SUCCESS: LAG peaked in Q3 2008 (The Fed Trap is confirmed).")
    else:
        LOG.warning(f"⚠️ MARGINAL: Peak was {peak_date.date()}, target was Q3 2008.")

def save_results(df):
    LOG.info(f"Saving LAG model to {OUTPUT_FILE}...")
    
    # Save selected columns
    cols = [
        'lag_composite', 'signal_line', 
        'cpi_serv_yoy', 'unrate_inverted', 'ulc_yoy', 'loans_yoy',
        'z_cpi', 'z_unrate', 'z_ulc', 'z_loans'
    ]
    df[cols].to_parquet(OUTPUT_FILE)
    LOG.info("LAG model saved successfully.")

def main():
    try:
        df = calculate_lag_index()
        
        # Validate logic
        validate_fed_trap(df)
        
        print("\n" + "="*50)
        print("Lagging Economic Indicator (LAG): Inertia Model")
        print("="*50)
        print(df[['lag_composite', 'signal_line']].tail(5))
        print("="*50 + "\n")
        
        save_results(df)
        LOG.info("LAG Index generation complete!")
        
    except Exception as e:
        LOG.error(f"Failed to generate LAG Index: {e}")
        exit(1)

if __name__ == "__main__":
    main()
