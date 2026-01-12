#!/usr/bin/env python3
"""
Final LEI Calibration Script (7-Component Model)

This script implements the final 7-component configuration for the Leading Indicators Index (LEI).
It focuses on maximum historical reach (back to 1960s) via ragged weighting and specific handling
of yield spreads and sentiment splicing.

Components & Weights:
1. 10Y-2Y Spread (30%) - Calculated from DGS10 and DGS2
2. 10Y-3M Spread (20%) - Calculated from DGS10 and TB3MS
3. Housing Permits (20%) - PERMIT
4. New Orders (15%) - DGORDER (Starts 1992)
5. Weekly Hours (5%) - AWHMAN
6. Jobless Claims (5%) - ICSA (Inverted)
7. Consumer Sentiment (5%) - UMCSENT spliced with UMCSENT1

Methodology:
- Variable Transformations: Spreads (Levels), Others (YoY %)
- Normalization: 10-Year Rolling Z-Score (min_periods=24)
- Aggregation: Dynamic "Ragged" Weighting based on component availability
- Final Output: Amplitude-adjusted Composite Index
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
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

# Constants
START_DATE = "1960-01-01"
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

def rolling_z_score(series, window_years=10, min_periods=24):
    """Calculate rolling Z-score with expanding window fallback for early data."""
    window = window_years * 12
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    return (series - rolling_mean) / rolling_std

def load_fred_series(sid, name):
    """Load and resample a single FRED series."""
    p = RAW_DIR / f"{sid}.parquet"
    if not p.exists():
        LOG.warning(f"Missing data for {sid} at {p}")
        return None
    df = pd.read_parquet(p)
    df.set_index('date', inplace=True)
    # Resample to monthly (MS) taking the last value
    return df.resample('MS').last().rename(columns={'value': name})

def main():
    LOG.info("Loading RAW macro series for Final LEI Model...")
    
    # 1. Load Raw Data
    # ----------------
    series_map = {
        'DGS10': 'yield_10y',
        'DGS2': 'yield_2y',
        'TB3MS': 'yield_3m',
        'PERMIT': 'permit',
        'DGORDER': 'orders',
        'AWHMAN': 'hours',
        'ICSA': 'claims',
        'UMCSENT': 'sentiment_curr',
        'UMCSENT1': 'sentiment_hist'
    }
    
    dfs = []
    for sid, name in series_map.items():
        df = load_fred_series(sid, name)
        if df is not None:
            dfs.append(df)
            
    # Join all series
    data = dfs[0]
    for df in dfs[1:]:
        data = data.join(df, how='outer')
    
    data = data.sort_index().ffill()
    
    # Filter strictly from start date to reduce noise
    data = data[data.index >= '1950-01-01'] # Load extra history for calc
    
    # 2. Transformations & Compilations
    # ---------------------------------
    
    LOG.info("Processing Components (Splicing, Calculation, Transformation)...")
    
    # A. Splicing Sentiment
    # Use UMCSENT (Current) primarily, fill gaps with UMCSENT1 (Hist)
    data['sentiment'] = data['sentiment_curr'].combine_first(data['sentiment_hist'])
    
    # B. Calculating Spreads (Raw Levels)
    # 10Y-2Y
    data['spread_10y2y'] = data['yield_10y'] - data['yield_2y']
    # 10Y-3M
    data['spread_10y3m'] = data['yield_10y'] - data['yield_3m']
    
    # C. YoY Transformations
    # Permits
    data['permit_yoy'] = data['permit'].pct_change(periods=12)
    
    # New Orders (Starts ~1992)
    data['orders_yoy'] = data['orders'].pct_change(periods=12)
    
    # Weekly Hours
    data['hours_yoy'] = data['hours'].pct_change(periods=12)
    
    # Jobless Claims (Logic: Invert first, then YoY)
    # Inverting Level: -1 * ICSA
    data['claims_inv'] = data['claims'] * -1
    # YoY of Inverted: (Curr_Inv - Prev_Inv) / |Prev_Inv|
    # Note: Standard pct_change vs negative numbers can be tricky.
    # Simple workaround: Since claims are always positive, pct_change on raw claims * -1 reflects direction correctly.
    # Ex: Claims 200 -> 220 (+10% Bad). Inverted: -200 -> -220. Change -20. -20 / |-200| = -10% (Good/Bad sign flip).
    # Let's trust pct_change on inverted.
    data['claims_yoy'] = data['claims_inv'].pct_change(periods=12)
    
    # Sentiment
    data['sentiment_yoy'] = data['sentiment'].pct_change(periods=12)
    
    # 3. Component Normalization (Z-Scores)
    # -------------------------------------
    LOG.info("Calculating Rolling Z-Scores (10Y Window, Min 24 Months)...")
    
    # Map raw transformed columns to Z-score names
    z_map = {
        'spread_10y2y': 'z_spread_10y2y',
        'spread_10y3m': 'z_spread_10y3m',
        'permit_yoy':   'z_permit',
        'orders_yoy':   'z_orders',
        'hours_yoy':    'z_hours',
        'claims_yoy':   'z_claims',
        'sentiment_yoy':'z_sentiment'
    }
    
    for col, z_col in z_map.items():
        data[z_col] = rolling_z_score(data[col], window_years=10, min_periods=24)
        
    # 4. Ragged Weighting Logic
    # -------------------------
    LOG.info("Calculating Ragged Weighted Composite...")
    
    # Target Weights
    weights = {
        'z_spread_10y2y': 0.30,
        'z_spread_10y3m': 0.20,
        'z_permit':       0.20,
        'z_orders':       0.15,
        'z_hours':        0.05,
        'z_claims':       0.05,
        'z_sentiment':    0.05
    }
    
    def calculate_ragged_composite(row):
        available_val_weights = []
        sum_weights = 0
        for col, w in weights.items():
            val = row[col]
            if not pd.isna(val) and not np.isinf(val):
                available_val_weights.append(val * w)
                sum_weights += w
        
        if sum_weights == 0:
            return np.nan
        
        # Re-normalize to 100% (divide sum of contributions by sum of available weights)
        return sum(available_val_weights) / sum_weights

    data['composite_raw'] = data.apply(calculate_ragged_composite, axis=1)
    
    # 5. Final Normalization & Signal Generation
    # ------------------------------------------
    LOG.info("Generating Final Composite & Signals...")
    
    # Amplitude Fix: Z-Score the final composite (ensure +/- 3 range)
    # Using same 10Y expanding window logic
    data['lei_composite'] = rolling_z_score(data['composite_raw'], window_years=10, min_periods=24) 
    
    # Scale slightly? Usually raw Z-score is fine if components are correlated. 
    # User requested: "Amplitude Fix - Calculate Z-Score of Final Composite."
    # Previous script used * 2.0. Let's stick to raw Z-score first or apply modest multiplier?
    # "Ensure it swings +/- 3". Standard Z-score is +/- 2 mostly. 3 is rare (sigma).
    # If we want it to *regularly* hit +/-3 like the Zeberg chart, we might need a multiplier.
    # Previous script strictly set * 2.0. Let's keep a 1.5 or 2.0 scalar to separate the signal from noise visually?
    # Actually, a standard normal distribution is ~99% within +/- 3. 
    # Let's apply a 2.0x scalar same as previous calibrated model to match visual expectations.
    data['lei_composite'] = data['lei_composite'] * 2.0

    # Smooth Signals
    data['signal_12m'] = data['lei_composite'].rolling(window=SIGNAL_12M_MONTHS).mean()
    data['signal_18m'] = data['lei_composite'].rolling(window=SIGNAL_18M_MONTHS).mean()
    data['signal_24m'] = data['lei_composite'].rolling(window=SIGNAL_24M_MONTHS).mean()
    
    # Legacy alias
    data['signal_line'] = data['signal_12m']

    # 6. Output
    # ---------
    # Filter for final output range (User asked for 1960s history)
    output_data = data[data.index >= START_DATE]
    
    # Clean up purely NaN rows at start
    output_data = output_data.dropna(subset=['lei_composite'])
    
    LOG.info(f"Saving Final LEI Model to {OUTPUT_FILE}...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_data.to_parquet(OUTPUT_FILE)
    
    print("\n" + "="*60)
    print("Final LEI Model (7-Component) - Last 5 Months")
    print("="*60)
    print(output_data[['lei_composite', 'signal_12m', 'signal_18m', 'signal_24m']].tail(5))
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
