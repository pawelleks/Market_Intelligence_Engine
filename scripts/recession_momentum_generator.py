#!/usr/bin/env python3
"""
Macro-Momentum Recession Model Generator

This script fetches the 'All Employees, Total Nonfarm' (PAYEMS) series from FRED,
calculates the month-over-month job growth, computes a 12-month SMA (Trend Line),
and determines the recession signal based on the 'Stall Speed' threshold of 97,000 jobs.

Output: data/processed/recession_momentum.parquet
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
STALL_SPEED_THRESHOLD = 97000  # 97k jobs
START_YEAR = "1970-01-01"
SERIES_ID = "PAYEMS"

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
RAW_MACRO_DIR = BASE_DIR / "data" / "raw" / "macro" / "fred"
OUTPUT_FILE = PROCESSED_DATA_DIR / "recession_momentum.parquet"

# FRED API
# FRED_API_KEY = os.getenv("FRED_API_KEY")
# if not FRED_API_KEY:
#     raise ValueError("FRED_API_KEY not found in environment variables")

# fred = Fred(api_key=FRED_API_KEY)

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

def fetch_payroll_data():
    """Load NFP (PAYEMS) data from cache."""
    try:
        LOG.info(f"Loading {SERIES_ID} from cache...")
        series = load_cached_series(SERIES_ID)
        # Use to_frame to preserve index and rename column correctly
        df = series.to_frame(name='payroll_thousands')
        LOG.info(f"Successfully loaded {len(df)} observations from cache.")
        return df
    except Exception as e:
        LOG.error(f"Error loading data from cache: {e}")
        raise

def calculate_momentum_metrics(df):
    """
    Calculate MoM change, 12M SMA, and signals.
    """
    LOG.info("Calculating momentum metrics...")
    
    # 1. Calculate MoM change in absolute jobs (convert thousands to raw)
    # df['payroll_raw'] = df['payroll_thousands'] * 1000
    # df['nfp_mom'] = df['payroll_raw'].diff()
    
    # Actually, the requirement says "Calculate the MoM change in jobs (Raw NFP)".
    # If PAYEMS is in thousands (e.g., 150,000.0 means 150 million),
    # then diff() * 1000 gives absolute monthly job count change.
    df['nfp_mom'] = df['payroll_thousands'].diff() * 1000
    
    # 2. Calculate 12-Month SMA of MoM change
    df['nfp_sma_12m'] = df['nfp_mom'].rolling(window=12).mean()
    
    # 3. Signals and Regimes
    # Recession_Signal is TRUE when 12M SMA drops below 97,000
    df['recession_signal'] = df['nfp_sma_12m'] < STALL_SPEED_THRESHOLD
    
    # Regime: If 12M SMA > 97k set to "Expansion", else "Contraction/Risk"
    df['regime'] = np.where(df['nfp_sma_12m'] > STALL_SPEED_THRESHOLD, "Expansion", "Contraction/Risk")
    
    # Handle the initial NaN values from diff and rolling
    df = df.dropna(subset=['nfp_sma_12m'])
    
    return df

def save_results(df):
    """
    Save the processed data to a parquet file.
    """
    LOG.info(f"Saving results to {OUTPUT_FILE}...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_FILE)
    LOG.info("Results saved successfully.")

def main():
    try:
        # 1. Fetch data
        df = fetch_payroll_data()
        
        # 2. Process metrics
        df = calculate_momentum_metrics(df)
        
        # 3. Print verification
        print("\n" + "="*50)
        print("Macro-Momentum Recession Model: Last 5 Rows")
        print("="*50)
        # Using a subset of columns for readability
        print(df[['nfp_mom', 'nfp_sma_12m', 'recession_signal', 'regime']].tail(5))
        print("="*50 + "\n")
        
        # 4. Save results
        save_results(df)
        
        LOG.info("Macro-Momentum Recession Model calculation complete!")
        
    except Exception as e:
        LOG.error(f"Failed to generate model: {e}")
        exit(1)

if __name__ == "__main__":
    main()
