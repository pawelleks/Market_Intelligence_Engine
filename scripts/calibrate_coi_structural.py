#!/usr/bin/env python3
"""
Coincident Indicators Index (COI) - Reference 4-Factor Structural Model

This script implements the authoritative NBER-aligned COI model:
1. Employment (PAYEMS) - 35%
2. Production (INDPRO) - 25%
3. Real Income (W875RX1) - 20%
4. Real GDP (GDPC1) - 20%

Key Features:
- YoY % Change for all components
- 10-Year Rolling Z-Score normalization
- Dynamic weight redistribution for missing data
- Upsamples quarterly GDP to monthly
- Validates 2008 depth vs 2020

Output: data/analytics/macro/coi_model.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import sys
from fredapi import Fred
import os
from dotenv import load_dotenv
import ssl
import certifi
import urllib.request

# Setup paths
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mie_lib.utils.paths import DATA_DIR

# Define output directory
MACRO_ANALYSIS_DIR = DATA_DIR / "analytics" / "macro"
MACRO_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger("coi_structural")

# Constants
START_DATE = "1960-01-01"
ROLLING_WINDOW_YR = 10
ROLLING_WINDOW_MONTHS = ROLLING_WINDOW_YR * 12
MIN_PERIODS = 24  # Allow early start with partial window

# Component weights (Reference Model)
WEIGHTS = {
    'employment': 0.35,
    'production': 0.25,
    'real_income': 0.20,
    'real_gdp': 0.20
}

# FRED Series IDs
SERIES = {
    'employment': 'PAYEMS',      # All Employees, Total Nonfarm
    'production': 'INDPRO',      # Industrial Production: Total Index
    'real_income': 'W875RX1',    # Real Personal Income ex Transfers
    'real_gdp': 'GDPC1'          # Real GDP (Quarterly)
}

OUTPUT_FILE = MACRO_ANALYSIS_DIR / "coi_model.parquet"

# SSL Workaround for FRED API
try:
    context = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
    urllib.request.install_opener(opener)
except Exception as e:
    LOG.warning(f"SSL context setup failed: {e}")

# Initialize FRED API
FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY not found in environment variables")

fred = Fred(api_key=FRED_API_KEY)


def fetch_series(series_id, start_date=START_DATE):
    """Fetch a series from FRED."""
    LOG.info(f"Fetching {series_id}...")
    try:
        s = fred.get_series(series_id, observation_start=start_date)
        return pd.DataFrame(s, columns=[series_id])
    except Exception as e:
        LOG.error(f"Failed to fetch {series_id}: {e}")
        raise


def upsample_gdp_to_monthly(gdp_quarterly):
    """
    Convert quarterly GDP to monthly frequency using forward fill.
    This is acceptable for coincident indicators as it reflects the
    economic state during each quarter.
    """
    LOG.info("Upsampling quarterly GDP to monthly...")
    # Resample to month-start, forward fill the quarterly values
    monthly = gdp_quarterly.resample('MS').ffill()
    return monthly


def calculate_yoy_pct_change(series, periods=12):
    """Calculate Year-over-Year percentage change."""
    return series.pct_change(periods=periods)


def rolling_z_score(series, window_months=ROLLING_WINDOW_MONTHS, min_periods=MIN_PERIODS, cap=3.5):
    """
    Calculate rolling Z-score with specified window and outlier capping.
    Capping ensures that extreme transient events (like COVID 2020) 
    don't statistically disappear more structural systemic events (like GFC 2008).
    """
    rolling_mean = series.rolling(window=window_months, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window_months, min_periods=min_periods).std()
    z = (series - rolling_mean) / rolling_std
    
    # Apply cap to handle statistical outliers
    return z.clip(lower=-cap, upper=cap)


def redistribute_weights(available_components):
    """
    Dynamically redistribute weights when components are missing.
    Proportionally allocate missing weight to available components.
    """
    available_weights = {k: v for k, v in WEIGHTS.items() if k in available_components}
    total_available = sum(available_weights.values())
    
    if total_available == 0:
        return {}
    
    # Normalize to sum to 1.0
    return {k: v / total_available for k, v in available_weights.items()}


def calculate_coi_structural():
    """
    Calculate the 4-Factor COI Structural Model.
    """
    LOG.info("="*60)
    LOG.info("Starting COI 4-Factor Reference Model Calculation")
    LOG.info("="*60)
    
    # 1. Fetch Raw Data
    employment = fetch_series(SERIES['employment'])
    production = fetch_series(SERIES['production'])
    real_income = fetch_series(SERIES['real_income'])
    gdp_quarterly = fetch_series(SERIES['real_gdp'])
    
    # 2. Upsample GDP from quarterly to monthly
    gdp_monthly = upsample_gdp_to_monthly(gdp_quarterly)
    
    # 3. Merge all components
    df = employment.join([production, real_income, gdp_monthly], how='outer')
    df = df.resample('MS').last()  # Ensure month-start index
    
    # 4. Calculate YoY % Change for all components
    LOG.info("Calculating Year-over-Year growth rates...")
    df['employment_yoy'] = calculate_yoy_pct_change(df[SERIES['employment']])
    df['production_yoy'] = calculate_yoy_pct_change(df[SERIES['production']])
    df['real_income_yoy'] = calculate_yoy_pct_change(df[SERIES['real_income']])
    df['real_gdp_yoy'] = calculate_yoy_pct_change(df[SERIES['real_gdp']])
    
    # 5. Normalize with 10-Year Rolling Z-Score
    LOG.info(f"Applying {ROLLING_WINDOW_YR}-year rolling Z-score normalization...")
    df['z_employment'] = rolling_z_score(df['employment_yoy'])
    df['z_production'] = rolling_z_score(df['production_yoy'])
    df['z_real_income'] = rolling_z_score(df['real_income_yoy'])
    df['z_real_gdp'] = rolling_z_score(df['real_gdp_yoy'])
    
    # 6. Calculate weighted composite with dynamic weight redistribution
    LOG.info("Calculating weighted composite index...")
    
    z_components = ['z_employment', 'z_production', 'z_real_income', 'z_real_gdp']
    component_names = ['employment', 'production', 'real_income', 'real_gdp']
    
    # Row-wise composite calculation with dynamic weights
    def calc_weighted_composite(row):
        # Find available components (non-NaN)
        available = [name for i, name in enumerate(component_names) if not pd.isna(row[z_components[i]])]
        
        if not available:
            return np.nan
        
        # Get redistributed weights
        weights = redistribute_weights(available)
        
        # Calculate weighted sum
        total = 0.0
        for i, name in enumerate(component_names):
            if name in available:
                total += row[z_components[i]] * weights[name]
        
        return total
    
    df['coi_composite'] = df.apply(calc_weighted_composite, axis=1)
    
    # 7. Add signal line (3-month SMA)
    df['signal_line'] = df['coi_composite'].rolling(3).mean()
    
    # 8. Store z-scores and weights for component analysis
    df['weight_employment'] = WEIGHTS['employment']
    df['weight_production'] = WEIGHTS['production']
    df['weight_real_income'] = WEIGHTS['real_income']
    df['weight_real_gdp'] = WEIGHTS['real_gdp']
    
    return df


def validate_depth(df):
    """
    Validate that 2008 crisis depth is properly captured.
    Compare 2008 vs 2020 minimum values.
    """
    LOG.info("="*60)
    LOG.info("VALIDATION: Comparing Crisis Depths")
    LOG.info("="*60)
    
    # 2008 Financial Crisis (Sep 2008 - Jun 2009)
    crisis_2008 = df.loc['2008-01-01':'2009-12-31', 'coi_composite']
    if not crisis_2008.empty:
        min_2008 = crisis_2008.min()
        date_2008 = crisis_2008.idxmin()
        LOG.info(f"  2008 Crisis Min: {min_2008:.4f} on {date_2008.strftime('%Y-%m')}")
    else:
        LOG.warning("  No data for 2008 crisis period")
        min_2008 = None
    
    # 2020 COVID (Mar 2020 - May 2020)
    crisis_2020 = df.loc['2020-01-01':'2020-12-31', 'coi_composite']
    if not crisis_2020.empty:
        min_2020 = crisis_2020.min()
        date_2020 = crisis_2020.idxmin()
        LOG.info(f"  2020 COVID Min: {min_2020:.4f} on {date_2020.strftime('%Y-%m')}")
    else:
        LOG.warning("  No data for 2020 crisis period")
        min_2020 = None
    
    if min_2008 is not None and min_2020 is not None:
        if min_2008 < min_2020:
            LOG.info(f"  ✅ SUCCESS: 2008 crisis depth ({min_2008:.4f}) < 2020 ({min_2020:.4f})")
        else:
            LOG.warning(f"  ⚠️  2008 depth ({min_2008:.4f}) >= 2020 ({min_2020:.4f})")
        
        LOG.info(f"  Depth Ratio: {min_2008/min_2020:.2f}x")
    
    LOG.info("="*60)


def save_results(df):
    """Save COI model to parquet."""
    LOG.info(f"Saving COI model to {OUTPUT_FILE}...")
    
    # Select columns to save
    save_cols = [
        'coi_composite', 'signal_line',
        # Raw series
        SERIES['employment'], SERIES['production'], SERIES['real_income'], SERIES['real_gdp'],
        # YoY growth
        'employment_yoy', 'production_yoy', 'real_income_yoy', 'real_gdp_yoy',
        # Z-scores
        'z_employment', 'z_production', 'z_real_income', 'z_real_gdp',
        # Weights
        'weight_employment', 'weight_production', 'weight_real_income', 'weight_real_gdp'
    ]
    
    df[save_cols].to_parquet(OUTPUT_FILE)
    LOG.info("✅ COI model saved successfully")
    
    # Print summary
    print("\n" + "="*60)
    print("COI 4-Factor Reference Model - Latest Values")
    print("="*60)
    print(df[['coi_composite', 'signal_line']].tail(6))
    print("="*60 + "\n")


def main():
    try:
        # Calculate model
        df = calculate_coi_structural()
        
        # Validate
        validate_depth(df)
        
        # Save
        save_results(df)
        
        LOG.info("COI 4-Factor Reference Model generation complete!")
        
    except Exception as e:
        LOG.error(f"Failed to generate COI model: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
