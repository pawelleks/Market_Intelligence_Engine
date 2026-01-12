#!/usr/bin/env python3
"""
Leading Indicators Index (LEI) Calibration Script.
Generates three candidate models (A, B, C) for comparison with +/- 3 Amplitude fix.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "macro" / "fred"
OUTPUT_FILE = BASE_DIR / "scripts" / "lei_calibration.parquet"

# Components
SERIES_MAP = {
    'T10Y2Y': 'yield_2y',
    'T10Y3M': 'yield_3m',
    'PERMIT': 'housing',
    'NEWORDER': 'orders',
    'SP500': 'sp500'
}

def rolling_z_score(series, window=120):
    """10-Year (120 Month) Rolling Z-Score."""
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    return (series - rolling_mean) / rolling_std

def z_score(series):
    """Full-History Z-Score."""
    return (series - series.mean()) / series.std()

def main():
    LOG.info("Loading RAW macro series...")
    dfs = []
    
    # Standard FRED series
    fred_series = {k: v for k, v in SERIES_MAP.items() if k != 'SP500'}
    for sid, name in fred_series.items():
        p = RAW_DIR / f"{sid}.parquet"
        if not p.exists():
            LOG.error(f"Missing data for {sid} at {p}")
            return
        df = pd.read_parquet(p)
        df.set_index('date', inplace=True)
        df = df.resample('MS').last().rename(columns={'value': name})
        dfs.append(df)

    # Local S&P 500 series (^GSPC)
    sp500_path = BASE_DIR / "data" / "raw" / "^GSPC.parquet"
    if sp500_path.exists():
        LOG.info(f"Using local SP500 data from {sp500_path}")
        df_sp = pd.read_parquet(sp500_path)
        df_sp.set_index('date', inplace=True)
        # Handle 'close' column
        df_sp = df_sp.resample('MS').last().rename(columns={'close': 'sp500'})
        dfs.append(df_sp[['sp500']])
    else:
        LOG.error(f"Missing local SP500 data at {sp500_path}")
        return

    # Join all data
    data = dfs[0]
    for df in dfs[1:]:
        data = data.join(df, how='outer')

    data = data.sort_index().ffill()

    LOG.info("Applying transformations...")
    # Transformations: Housing, Orders, SP500 -> YoY % Change
    data['housing_yoy'] = data['housing'].pct_change(periods=12)
    data['orders_yoy'] = data['orders'].pct_change(periods=12)
    data['sp500_yoy'] = data['sp500'].pct_change(periods=12)

    # Yields are kept as raw levels: yield_2y, yield_3m

    LOG.info("Calculating component Z-scores (5Y Rolling for Model A, 10Y for others)...")
    components = ['yield_2y', 'yield_3m', 'housing_yoy', 'orders_yoy', 'sp500_yoy']
    for col in components:
        # We'll keep the 120M column for B/C, but create a 60M one for A
        data[f'z_{col}_60'] = rolling_z_score(data[col], window=60)
        data[f'z_{col}_120'] = rolling_z_score(data[col], window=120)

    # Drop early NaNs
    data = data.dropna(subset=[f'z_{col}_120' for col in components])

    LOG.info("Generating Model Candidates...")

    # Define base weights (Shared with A and C)
    weights_heavy = {
        'yield_2y': 0.25,
        'yield_3m': 0.25,
        'housing_yoy': 0.25,
        'orders_yoy': 0.15,
        'sp500_yoy': 0.10
    }

    # Model-specific weight maps
    weights_a = {f'z_{k}_60': v for k, v in weights_heavy.items()}
    weights_bc = {f'z_{k}_120': v for k, v in weights_heavy.items()}
    weights_balanced_z = {f'z_{k}_120': 0.20 for k in weights_heavy.keys()}

    # --- Model A: Credit Heavy (Recommended) ---
    # Components: 6M SMA, Signal: 12M SMA
    # Applying 18M Lag to Yields to match Zeberg's Late 2024 crossover
    comp_a_raw = data[[k for k in weights_a.keys()]].rolling(window=6).mean()
    
    # Lag the yields specifically for Model A
    comp_a_raw['z_yield_2y_60'] = comp_a_raw['z_yield_2y_60'].shift(18)
    comp_a_raw['z_yield_3m_60'] = comp_a_raw['z_yield_3m_60'].shift(18)
    
    data['Model_A_Raw'] = sum(comp_a_raw[k] * w for k, w in weights_a.items())
    data['Model_A_Smooth'] = data['Model_A_Raw'].rolling(window=12).mean()
    # Post-Normalization (10-Year Rolling) + Amplitude Scaling (Increased to 2.0x to hit +/- 3)
    data['Model_A'] = rolling_z_score(data['Model_A_Smooth'], window=120) * 2.0

    # --- Model B: Balanced ---
    comp_b = data[[k for k in weights_balanced_z.keys()]].rolling(window=6).mean()
    data['Model_B_Raw'] = sum(comp_b[k] * w for k, w in weights_balanced_z.items())
    data['Model_B'] = z_score(data['Model_B_Raw']) * 1.5

    # --- Model C: Mega Smooth ---
    comp_c = data[[k for k in weights_bc.keys()]].rolling(window=12).mean()
    data['Model_C_Raw'] = sum(comp_c[k] * w for k, w in weights_bc.items())
    data['Model_C_Smooth'] = data['Model_C_Raw'].rolling(window=18).mean()
    data['Model_C'] = z_score(data['Model_C_Smooth']) * 1.5

    LOG.info("Calibration results generated with Post-Normalization and 1.5x Amplitude Scaling.")
    
    # Save results
    output_cols = ['Model_A', 'Model_B', 'Model_C']
    data[output_cols].dropna().to_parquet(OUTPUT_FILE)
    LOG.info(f"Saved results to {OUTPUT_FILE}")

    # Verification: Nov 2024 and Zero Cross
    try:
        verif_date = "2024-11-01"
        if verif_date in data.index:
            print("\n" + "="*50)
            print(f"VERIFICATION: READINGS FOR {verif_date}")
            print("="*50)
            print(data.loc[verif_date, output_cols])
            print("="*50)
            
            for m in output_cols:
                # Find the latest zero-cross (positive to negative)
                window_df = data[(data.index > '2022-01-01')]
                crossings = window_df[(window_df[m].shift(1) > 0) & (window_df[m] < 0)]
                last_cross = crossings.index[-1].strftime('%Y-%m') if not crossings.empty else "No Cross"
                print(f"{m} Zero Cross (Latest): {last_cross}")
            
            # Diagnostic for Model A components
            print("\n" + "="*50)
            print("MODEL A COMPONENT Z-SCORES (NOV 2024)")
            print("="*50)
            for k in weights_heavy.keys():
                print(f"{k}: {data.loc[verif_date, k]:.4f}")
            print("="*50)

            # Amplitude stats
            print("\n" + "="*50)
            print("AMPLITUDE ANALYSIS (1.5x Scaling Applied)")
            print("="*50)
            for m in output_cols:
                print(f"{m}: Min={data[m].min():.2f}, Max={data[m].max():.2f}")
            print("="*50)

        else:
            print(f"WARNING: Date {verif_date} not found in dataset. Last date is {data.index[-1]}")
    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    main()
