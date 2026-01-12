#!/usr/bin/env python3
"""
LAG Index Model Calibration Script - Confirmation Engine

Components:
1. CPI Services (Less Rent/Shelter) - CUSR0000SASL2RS
2. Unemployment Rate (Inverted) - UNRATE
3. Unit Labor Costs (Manufacturing) - ULCMFG
4. Commercial & Industrial Loans - BUSLOANS

Goal: Confirm these indicators peak 6-12 months AFTER the S&P 500.
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# Constants
START_YEAR = "1990-01-01"
ROLLING_WINDOW_YR = 5

# SSL Workaround
try:
    context = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
    urllib.request.install_opener(opener)
except Exception as e:
    LOG.warning(f"SSL context setup failed: {e}")

# FRED API
FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY not found in environment variables")

fred = Fred(api_key=FRED_API_KEY)

def fetch_series(series_id, start_date=START_YEAR):
    LOG.info(f"Fetching {series_id}...")
    s = fred.get_series(series_id, observation_start=start_date)
    return pd.DataFrame(s, columns=[series_id])

def rolling_z_score(series, window_years=5):
    window = window_years * 12
    return (series - series.rolling(window=window).mean()) / series.rolling(window=window).std()

def run_calibration():
    # 1. Fetch data
    cpi_serv = fetch_series("CUSR0000SASL2RS")
    unrate = fetch_series("UNRATE")
    ulc = fetch_series("ULCMFG")
    loans = fetch_series("BUSLOANS")
    sp500 = fetch_series("SP500")

    # 2. Alignment & Resampling
    # ULCMFG is quarterly, others monthly. Resample all to monthly.
    df = cpi_serv.join([unrate, ulc, loans, sp500], how='outer').resample('MS').last()
    
    # Simple linear interpolation for quarterly ULCMFG
    df['ULCMFG'] = df['ULCMFG'].interpolate(method='linear')
    
    # 3. Transformations
    # YoY for sticky stuff
    df['cpi_serv_yoy'] = df['CUSR0000SASL2RS'].pct_change(12)
    df['unrate_inverted'] = -df['UNRATE'] # Invert: lower unrate = higher index
    df['ulc_yoy'] = df['ULCMFG'].pct_change(12)
    df['loans_yoy'] = df['BUSLOANS'].pct_change(12)
    df['sp500_yoy'] = df['SP500'].pct_change(12)

    # 4. Normalization (Z-Score)
    cols_to_z = ['cpi_serv_yoy', 'unrate_inverted', 'ulc_yoy', 'loans_yoy']
    z_df = pd.DataFrame(index=df.index)
    for col in cols_to_z:
        z_df[f'z_{col}'] = rolling_z_score(df[col], ROLLING_WINDOW_YR)
    
    # Composite LAG Index
    z_df['lag_composite'] = z_df.mean(axis=1)
    
    # 5. Lag Analysis
    LOG.info("\n" + "="*60)
    LOG.info("LAGGING INDEX (LAG) CALIBRATION")
    LOG.info("="*60)
    
    # Correlation of LAG vs SP500 with various lags
    corrs = {}
    for l in range(-12, 13): # -12 to +12 months
        # Shift SP500 to see if LAG follows it
        # Positive lag l means SP500(t-l) corr with LAG(t)
        # If LAG peaks 6M AFTER SP500, then LAG(t) should correlate with SP500(t-6)
        corrs[l] = z_df['lag_composite'].corr(df['sp500_yoy'].shift(l))
    
    best_lag = max(corrs, key=lambda k: corrs[k])
    
    LOG.info(f"Max Correlation: {corrs[best_lag]:.4f} at shift {best_lag} months")
    LOG.info("Note: Positive shift means LAG follows SP500.")
    
    LOG.info("\nCorrelation Matrix (Monthly YoY):")
    LOG.info(df[['cpi_serv_yoy', 'unrate_inverted', 'ulc_yoy', 'loans_yoy', 'sp500_yoy']].corr())
    
    # 6. Integrity Check
    latest = z_df.iloc[-1]
    LOG.info("\nData Integrity Check (Latest Values):")
    LOG.info(latest)
    
    # Save for inspection
    output_path = Path("data/processed/lag_calibration.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    z_df.join(df[['sp500_yoy']]).to_parquet(output_path)
    LOG.info(f"\nResults saved to {output_path}")

if __name__ == "__main__":
    run_calibration()
