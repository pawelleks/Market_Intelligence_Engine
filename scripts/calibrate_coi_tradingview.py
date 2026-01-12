#!/usr/bin/env python3
"""
COI Model Calibration Script - TradingView Fingerprint Match

Objective: Reverse-engineer the TradingView Coincident Index where:
- 2008 Financial Crisis dip is DEEPER than 2020 COVID dip

Tests 3 candidate models:
- Model A: Smoothed NBER (4 components, 12M SMA)
- Model B: Cyclical/PMI Blend (2 components, 6M SMA)
- Model C: Credit Blend (2 components, 6M SMA)

Output: coi_calibration.parquet
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
START_YEAR = "1990-01-01"
ROLLING_WINDOW_YR = 5

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_FILE = PROCESSED_DATA_DIR / "coi_calibration.parquet"

# FRED API
FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY not found in environment variables")

fred = Fred(api_key=FRED_API_KEY)

def fetch_fred_series(series_id, start_date=START_YEAR):
    """Fetch a single FRED series."""
    try:
        LOG.info(f"Fetching {series_id}...")
        s = fred.get_series(series_id, observation_start=start_date)
        df = pd.DataFrame(s, columns=[series_id])
        return df
    except Exception as e:
        LOG.error(f"Error fetching {series_id}: {e}")
        raise

def rolling_z_score(series, window_years=5):
    """Calculate rolling Z-score."""
    window = window_years * 12
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    return (series - rolling_mean) / rolling_std

def calculate_model_a(start_date=START_YEAR):
    """
    Model A: Smoothed NBER
    Components: PAYEMS, W875RX1, INDPRO, CMRMTSPL
    Smoothing: 12-Month SMA before Z-scoring
    """
    LOG.info("=" * 60)
    LOG.info("MODEL A: Smoothed NBER (12M SMA)")
    LOG.info("=" * 60)
    
    # SSL Workaround
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
        urllib.request.install_opener(opener)
    except Exception as e:
        LOG.warning(f"SSL context setup failed: {e}")
    
    # Fetch all components
    payems = fetch_fred_series("PAYEMS", start_date)
    income = fetch_fred_series("W875RX1", start_date)
    indpro = fetch_fred_series("INDPRO", start_date)
    cmrmt = fetch_fred_series("CMRMTSPL", start_date)
    
    # Merge
    df = payems.join([income, indpro, cmrmt], how='outer')
    df = df.resample('MS').last()
    
    # YoY transformations
    df['payems_yoy'] = df['PAYEMS'].pct_change(periods=12)
    df['income_yoy'] = df['W875RX1'].pct_change(periods=12)
    df['indpro_yoy'] = df['INDPRO'].pct_change(periods=12)
    df['cmrmt_yoy'] = df['CMRMTSPL'].pct_change(periods=12)
    
    # Apply 12-Month SMA smoothing to YoY data
    LOG.info("Applying 12-Month SMA smoothing...")
    df['payems_smooth'] = df['payems_yoy'].rolling(window=12).mean()
    df['income_smooth'] = df['income_yoy'].rolling(window=12).mean()
    df['indpro_smooth'] = df['indpro_yoy'].rolling(window=12).mean()
    df['cmrmt_smooth'] = df['cmrmt_yoy'].rolling(window=12).mean()
    
    # Drop NaN rows
    df = df.dropna(subset=['payems_smooth', 'income_smooth', 'indpro_smooth', 'cmrmt_smooth'])
    
    # Z-Score normalization (5-year rolling)
    df['z_payems'] = rolling_z_score(df['payems_smooth'], ROLLING_WINDOW_YR)
    df['z_income'] = rolling_z_score(df['income_smooth'], ROLLING_WINDOW_YR)
    df['z_indpro'] = rolling_z_score(df['indpro_smooth'], ROLLING_WINDOW_YR)
    df['z_cmrmt'] = rolling_z_score(df['cmrmt_smooth'], ROLLING_WINDOW_YR)
    
    # Composite: Equal-weighted average
    df['Model_A'] = (df['z_payems'] + df['z_income'] + df['z_indpro'] + df['z_cmrmt']) / 4
    
    df = df.dropna(subset=['Model_A'])
    LOG.info(f"Model A generated: {len(df)} rows")
    
    return df[['Model_A']]

def calculate_model_b(start_date=START_YEAR):
    """
    Model B: Cyclical/PMI Blend
    Components: PAYEMS, HTRUCKSSAAR
    Smoothing: 6-Month SMA before Z-scoring
    """
    LOG.info("=" * 60)
    LOG.info("MODEL B: Cyclical/PMI Blend (6M SMA)")
    LOG.info("=" * 60)
    
    # SSL Workaround
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
        urllib.request.install_opener(opener)
    except Exception as e:
        LOG.warning(f"SSL context setup failed: {e}")
    
    # Fetch components
    payems = fetch_fred_series("PAYEMS", start_date)
    trucks = fetch_fred_series("HTRUCKSSAAR", start_date)
    
    # Merge
    df = payems.join(trucks, how='outer')
    df = df.resample('MS').last()
    
    # YoY transformations
    df['payems_yoy'] = df['PAYEMS'].pct_change(periods=12)
    df['trucks_yoy'] = df['HTRUCKSSAAR'].pct_change(periods=12)
    
    # Apply 6-Month SMA smoothing
    LOG.info("Applying 6-Month SMA smoothing...")
    df['payems_smooth'] = df['payems_yoy'].rolling(window=6).mean()
    df['trucks_smooth'] = df['trucks_yoy'].rolling(window=6).mean()
    
    df = df.dropna(subset=['payems_smooth', 'trucks_smooth'])
    
    # Z-Score normalization
    df['z_payems'] = rolling_z_score(df['payems_smooth'], ROLLING_WINDOW_YR)
    df['z_trucks'] = rolling_z_score(df['trucks_smooth'], ROLLING_WINDOW_YR)
    
    # Composite
    df['Model_B'] = (df['z_payems'] + df['z_trucks']) / 2
    
    df = df.dropna(subset=['Model_B'])
    LOG.info(f"Model B generated: {len(df)} rows")
    
    return df[['Model_B']]

def calculate_model_c(start_date=START_YEAR):
    """
    Model C: Credit Blend
    Components: PAYEMS, Credit Spread (BAA - DGS10, inverted)
    Smoothing: 6-Month SMA
    """
    LOG.info("=" * 60)
    LOG.info("MODEL C: Credit Blend (6M SMA)")
    LOG.info("=" * 60)
    
    # SSL Workaround
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
        urllib.request.install_opener(opener)
    except Exception as e:
        LOG.warning(f"SSL context setup failed: {e}")
    
    # Fetch components
    payems = fetch_fred_series("PAYEMS", start_date)
    baa = fetch_fred_series("BAA", start_date)
    dgs10 = fetch_fred_series("DGS10", start_date)
    
    # Merge
    df = payems.join([baa, dgs10], how='outer')
    df = df.resample('MS').last()
    
    # YoY for PAYEMS
    df['payems_yoy'] = df['PAYEMS'].pct_change(periods=12)
    
    # Credit spread (BAA - DGS10), inverted
    df['credit_spread'] = -(df['BAA'] - df['DGS10'])
    
    # Apply 6-Month SMA smoothing
    LOG.info("Applying 6-Month SMA smoothing...")
    df['payems_smooth'] = df['payems_yoy'].rolling(window=6).mean()
    df['spread_smooth'] = df['credit_spread'].rolling(window=6).mean()
    
    df = df.dropna(subset=['payems_smooth', 'spread_smooth'])
    
    # Z-Score normalization
    df['z_payems'] = rolling_z_score(df['payems_smooth'], ROLLING_WINDOW_YR)
    df['z_spread'] = rolling_z_score(df['spread_smooth'], ROLLING_WINDOW_YR)
    
    # Composite
    df['Model_C'] = (df['z_payems'] + df['z_spread']) / 2
    
    df = df.dropna(subset=['Model_C'])
    LOG.info(f"Model C generated: {len(df)} rows")
    
    return df[['Model_C']]

def validate_models(df):
    """
    Validate if 2008 crisis is deeper than 2020 COVID for each model.
    """
    LOG.info("\n" + "=" * 60)
    LOG.info("VALIDATION: 2008 vs 2020 Crisis Depth")
    LOG.info("=" * 60)
    
    # Define periods
    crisis_2008 = (df.index >= '2008-01-01') & (df.index <= '2009-12-31')
    crisis_2020 = (df.index >= '2020-01-01') & (df.index <= '2020-12-31')
    
    for col in ['Model_A', 'Model_B', 'Model_C']:
        if col not in df.columns:
            continue
            
        min_2008 = df.loc[crisis_2008, col].min()
        min_2020 = df.loc[crisis_2020, col].min()
        
        LOG.info(f"\n{col}:")
        LOG.info(f"  2008 Minimum: {min_2008:.4f}")
        LOG.info(f"  2020 Minimum: {min_2020:.4f}")
        
        if min_2008 < min_2020:
            LOG.info(f"  ✓ MATCH: 2008 is deeper ({min_2008:.4f} < {min_2020:.4f})")
        else:
            LOG.info(f"  ✗ MISMATCH: 2020 is deeper ({min_2020:.4f} < {min_2008:.4f})")
    
    LOG.info("=" * 60)

def main():
    """Generate all three models and save for comparison."""
    try:
        # Generate models
        model_a = calculate_model_a()
        model_b = calculate_model_b()
        model_c = calculate_model_c()
        
        # Merge all models on date
        df_combined = model_a.join([model_b, model_c], how='outer')
        df_combined = df_combined.sort_index()
        
        # Validate
        validate_models(df_combined)
        
        # Save results
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        df_combined.to_parquet(OUTPUT_FILE)
        LOG.info(f"\nCalibration results saved to: {OUTPUT_FILE}")
        
        # Print sample
        LOG.info("\nSample data (last 5 rows):")
        print(df_combined.tail())
        
    except Exception as e:
        LOG.error(f"Calibration failed: {e}")
        raise

if __name__ == "__main__":
    main()
