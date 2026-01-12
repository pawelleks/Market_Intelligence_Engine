#!/usr/bin/env python3
"""
Global Liquidity Impulse Calculator

This script calculates the Global Liquidity Index by aggregating major central bank
balance sheets (Fed, ECB, BoJ) normalized to USD, and computes the 3-month rate of
change as the "Liquidity Impulse" - a lead indicator for risk assets.

Output: liquidity_impulse.parquet with global liquidity and impulse metrics.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from fredapi import Fred
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
RAW_MACRO_DIR = BASE_DIR / "data" / "raw" / "macro" / "fred"
OUTPUT_FILE = PROCESSED_DATA_DIR / "liquidity_impulse.parquet"

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
    
    # Extract the value column
    if 'value' in df.columns:
        s = df['value']
    elif df.shape[1] == 1:
        s = df.iloc[:, 0]
    else:
        raise ValueError(f"Unexpected DataFrame structure for {series_id}")
    
    # Return as Series with proper DatetimeIndex
    s.name = series_id
    return s

def fetch_central_bank_data():
    """Load central bank balance sheet data from cache."""
    LOG.info("Loading central bank balance sheet data from cache...")
    
    # FRED Series IDs
    series_map = {
        'fed_assets': 'WALCL',           # Federal Reserve Total Assets (Millions USD)
        'ecb_assets': 'ECBASSETS',       # ECB Total Assets (Millions EUR)
        'boj_assets': 'JPNASSETS',       # Bank of Japan Total Assets (100 Million JPY units)
        'eurusd': 'DEXUSEU',             # USD per 1 EUR
        'usdjpy': 'DEXJPUS',             # JPY per 1 USD
    }
    
    data = {}
    
    for name, series_id in series_map.items():
        try:
            LOG.info(f"Loading {name} ({series_id}) from cache...")
            series = load_cached_series(series_id)
            data[name] = series
            LOG.info(f"  → {len(series)} observations from {series.index[0]} to {series.index[-1]}")
        except Exception as e:
            LOG.warning(f"Could not load {name} ({series_id}): {e}")
            data[name] = pd.Series(dtype=float)
    
    # Combine into DataFrame
    df = pd.DataFrame(data)
    
    # Forward-fill missing values (weekends, holidays)
    df = df.ffill()
    
    # Drop rows where any critical series is missing
    critical_cols = ['fed_assets', 'ecb_assets', 'boj_assets', 'eurusd', 'usdjpy']
    df = df.dropna(subset=critical_cols)
    
    if len(df) == 0:
        raise ValueError("No valid data found. Check FRED data cache.")
    
    LOG.info(f"Combined dataset: {len(df)} observations")
    
    return df


def normalize_to_usd(df):
    """
    Convert all central bank assets to USD.
    
    Args:
        df: DataFrame with raw assets and exchange rates
        
    Returns:
        pd.DataFrame: DataFrame with USD-normalized assets
    """
    LOG.info("Normalizing all assets to USD...")
    
    if len(df) == 0:
        raise ValueError("Cannot normalize empty dataset")
    
    result = pd.DataFrame(index=df.index)
    
    # Fed is already in millions USD
    result['fed_assets_usd'] = df['fed_assets'] / 1000  # Convert to billions
    
    # ECB: Convert millions EUR to billions USD
    # DEXUSEU gives USD per 1 EUR, so multiply EUR by this rate
    result['ecb_assets_usd'] = (df['ecb_assets'] / 1000) * df['eurusd']
    
    # BoJ: Convert from 100 Million JPY units to Billions USD
    # Step 1: Raw FRED value is in 100 Million Yen units
    # Step 2: Multiply by 100,000,000 to get total Yen, then divide by 1,000,000,000 to get Billions Yen
    #         This simplifies to: value / 10
    # Step 3: DEXJPUS gives JPY per 1 USD, so divide by this rate to get Billions USD
    result['boj_assets_usd'] = (df['boj_assets'] / 10) / df['usdjpy']
    
    if len(result) > 0:
        LOG.info("Currency normalization complete.")
        LOG.info(f"  Fed (latest): ${result['fed_assets_usd'].iloc[-1]:.2f}B")
        LOG.info(f"  ECB (latest): ${result['ecb_assets_usd'].iloc[-1]:.2f}B")
        LOG.info(f"  BoJ (latest): ${result['boj_assets_usd'].iloc[-1]:.2f}B")
    
    return result


def calculate_global_liquidity(df):
    """
    Aggregate central bank assets into Global Liquidity Index.
    
    Args:
        df: DataFrame with USD-normalized assets
        
    Returns:
        pd.DataFrame: DataFrame with global liquidity metrics
    """
    LOG.info("Calculating Global Liquidity Index...")
    
    # Aggregate: Sum of all central bank balance sheets
    df['global_liquidity'] = (
        df['fed_assets_usd'] + 
        df['ecb_assets_usd'] + 
        df['boj_assets_usd']
    )
    
    # Apply 4-week (28-day) moving average to smooth reporting noise
    df['global_liquidity_smooth'] = df['global_liquidity'].rolling(window=28, min_periods=1).mean()
    
    LOG.info(f"Global Liquidity (latest): ${df['global_liquidity_smooth'].iloc[-1]:.2f}B (${df['global_liquidity_smooth'].iloc[-1]/1000:.2f}T)")
    
    return df


def calculate_impulse(df):
    """
    Calculate the 3-month (90-day) rate of change as the Liquidity Impulse.
    
    Formula: (Current / Value_90_days_ago) - 1
    
    Args:
        df: DataFrame with global_liquidity_smooth
        
    Returns:
        pd.DataFrame: DataFrame with impulse metric
    """
    LOG.info("Calculating 3-month Liquidity Impulse (rate of change)...")
    
    # 3-month lookback (approximately 90 days)
    lookback = 90
    
    # Calculate percentage change
    df['liquidity_impulse'] = df['global_liquidity_smooth'].pct_change(periods=lookback) * 100
    
    # Get latest impulse
    latest_impulse = df['liquidity_impulse'].iloc[-1]
    
    if pd.notna(latest_impulse):
        direction = "Expanding" if latest_impulse > 0 else "Contracting"
        LOG.info(f"Liquidity Impulse (3M): {latest_impulse:+.2f}% ({direction})")
    else:
        LOG.warning("Latest impulse is NaN (insufficient data)")
    
    return df


def save_results(df):
    """
    Save results to parquet file.
    
    Args:
        df: DataFrame with all liquidity metrics
    """
    LOG.info(f"Saving results to {OUTPUT_FILE}...")
    
    # Select final columns
    output_cols = [
        'fed_assets_usd',
        'ecb_assets_usd', 
        'boj_assets_usd',
        'global_liquidity',
        'global_liquidity_smooth',
        'liquidity_impulse'
    ]
    
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to parquet
    df[output_cols].to_parquet(OUTPUT_FILE)
    
    LOG.info(f"Results saved successfully.")


def main():
    """
    Main execution function.
    """
    LOG.info("Initializing Global Liquidity Impulse Calculation...")
    
    try:
        # 1. Fetch central bank data
        raw_data = fetch_central_bank_data()
        
        # 2. Normalize to USD
        usd_data = normalize_to_usd(raw_data)
        
        # 3. Calculate global liquidity
        liquidity_data = calculate_global_liquidity(usd_data)
        
        # 4. Calculate impulse
        final_data = calculate_impulse(liquidity_data)
        
        # 5. Save results
        save_results(final_data)
        
        # 6. Print summary
        latest = final_data.iloc[-1]
        latest_date = final_data.index[-1]
        
        print("\n" + "="*80)
        print("Global Liquidity Impulse: Latest Results")
        print("="*80)
        print(f"Date:                     {latest_date.strftime('%Y-%m-%d')}")
        print(f"Global Liquidity:         ${latest['global_liquidity_smooth']:.2f}B (${latest['global_liquidity_smooth']/1000:.2f}T)")
        print(f"  ├─ Fed:                 ${latest['fed_assets_usd']:.2f}B")
        print(f"  ├─ ECB:                 ${latest['ecb_assets_usd']:.2f}B")
        print(f"  └─ BoJ:                 ${latest['boj_assets_usd']:.2f}B")
        print(f"3-Month Impulse:          {latest['liquidity_impulse']:+.2f}%")
        
        direction = "Expanding" if latest['liquidity_impulse'] > 0 else "Contracting"
        print(f"Status:                   {direction}")
        print("="*80)
        print()
        
        LOG.info("Global Liquidity Impulse calculation complete!")
        
    except Exception as e:
        LOG.error(f"Error during Global Liquidity calculation: {e}")
        raise


if __name__ == "__main__":
    main()
