#!/usr/bin/env python3
"""
COI Model Calibration Script v2 - Aggressive Fingerprint Matching

Matches specific TradingView profile:
1. 2008 dip at least 2x deeper than any other.
2. 2020 dip is the shallowest/barely visible.
3. Huge upward spike in 2021/2022.
4. "Lazy" signal line (24M SMA).

Tests:
- Model A: NBER components, 18M SMA.
- Model B: Production + Retail, 12M SMA.
- Model C: Production + Retail, 18M SMA.
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
SIGNAL_SMA = 24

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
    # Fetch all data
    payems = fetch_series("PAYEMS")
    indpro = fetch_series("INDPRO")
    income = fetch_series("W875RX1")
    cmrmt = fetch_series("CMRMTSPL")
    rrsfs = fetch_series("RRSFS") # Real Retail and Food Services Sales

    df = payems.join([indpro, income, cmrmt, rrsfs], how='outer').resample('MS').last()
    
    # Calculate YoY raw
    df['payems_yoy'] = df['PAYEMS'].pct_change(12)
    df['indpro_yoy'] = df['INDPRO'].pct_change(12)
    df['income_yoy'] = df['W875RX1'].pct_change(12)
    df['cmrmt_yoy'] = df['CMRMTSPL'].pct_change(12)
    df['rrsfs_yoy'] = df['RRSFS'].pct_change(12)

    results = pd.DataFrame(index=df.index)

    # Model A: NBER components, 18M SMA
    comp_a = (df[['payems_yoy', 'indpro_yoy', 'income_yoy', 'cmrmt_yoy']]
              .rolling(18).mean()
              .dropna())
    z_a = comp_a.apply(lambda x: rolling_z_score(x, ROLLING_WINDOW_YR))
    results['Model_A'] = z_a.mean(axis=1)
    results['Signal_A'] = results['Model_A'].rolling(SIGNAL_SMA).mean()

    # Model B: Production + Retail, 12M SMA
    comp_b = (df[['indpro_yoy', 'rrsfs_yoy']]
              .rolling(12).mean()
              .dropna())
    z_b = comp_b.apply(lambda x: rolling_z_score(x, ROLLING_WINDOW_YR))
    results['Model_B'] = z_b.mean(axis=1)
    results['Signal_B'] = results['Model_B'].rolling(SIGNAL_SMA).mean()

    # Model C: Production + Retail, 18M SMA
    comp_c = (df[['indpro_yoy', 'rrsfs_yoy']]
              .rolling(18).mean()
              .dropna())
    z_c = comp_c.apply(lambda x: rolling_z_score(x, ROLLING_WINDOW_YR))
    results['Model_C'] = z_c.mean(axis=1)
    results['Signal_C'] = results['Model_C'].rolling(SIGNAL_SMA).mean()

    # Model D: Production + Retail, 24M SMA, 15Y Z-score (Fixed Std Dev)
    comp_d = (df[['indpro_yoy', 'rrsfs_yoy']]
              .rolling(24).mean()
              .dropna())
    # 15 Year Z-score to normalize by a long-term average (pre-COVID volatility)
    z_d = comp_d.apply(lambda x: rolling_z_score(x, 15))
    results['Model_D'] = z_d.mean(axis=1)
    results['Signal_D'] = results['Model_D'].rolling(SIGNAL_SMA).mean()

    # Analysis
    LOG.info("\n" + "="*60)
    LOG.info("CALIBRATION V2 RESULTS")
    LOG.info("="*60)

    periods = {
        '1990': ('1990-01-01', '1992-12-31'),
        '2001': ('2001-01-01', '2002-12-31'),
        '2008': ('2008-01-01', '2009-12-31'),
        '2020': ('2020-01-01', '2020-12-31'),
        '2022_Spike': ('2021-01-01', '2022-12-31')
    }

    for model in ['Model_A', 'Model_B', 'Model_C', 'Model_D']:
        m_data = results[model].dropna()
        if m_data.empty: continue

        min_1990 = results.loc[periods['1990'][0]:periods['1990'][1], model].min()
        min_2001 = results.loc[periods['2001'][0]:periods['2001'][1], model].min()
        min_2008 = results.loc[periods['2008'][0]:periods['2008'][1], model].min()
        min_2020 = results.loc[periods['2020'][0]:periods['2020'][1], model].min()
        max_2022 = results.loc[periods['2022_Spike'][0]:periods['2022_Spike'][1], model].max()
        
        ratio = abs(min_2008 / min_2020) if min_2020 != 0 else 0
        
        LOG.info(f"\n{model}:")
        LOG.info(f"  1990 Depth: {min_1990:.4f}")
        LOG.info(f"  2001 Depth: {min_2001:.4f}")
        LOG.info(f"  2008 Depth: {min_2008:.4f}")
        LOG.info(f"  2020 Depth: {min_2020:.4f}")
        LOG.info(f"  Ratio (2008/2020): {ratio:.2f} {'(GOAL: > 2.0)' if ratio > 2.0 else ''}")
        LOG.info(f"  2022 Max Spike: {max_2022:.4f}")

    LOG.info("="*60)
    
    # Save
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    results.to_parquet(processed_dir / "coi_calibration_v2.parquet")
    LOG.info(f"Saved to {processed_dir / 'coi_calibration_v2.parquet'}")

if __name__ == "__main__":
    run_calibration()
