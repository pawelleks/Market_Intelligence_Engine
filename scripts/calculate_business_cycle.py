#!/usr/bin/env python3
"""
Calculate Business Cycle (LAG Indicator & Cycle Phases)

This script:
1. Calculates the Lagging Economic Indicator (LAG) using CPILFESL and UNRATE.
2. Combines it with existing LEI (Leading) and COI (Coincident) data.
3. Determines the "Cycle Phase" (Recovery, Expansion, Slowdown, Recession).
4. Analyzes S&P 500 correlation with LEI.

Methodology:
- LAG Components: Core CPI (YoY), Unemployment Rate (Level).
- LAG Aggregation: 0.5 * Z(CPI) + 0.5 * Z(UNRATE).
- Cycle Phases:
    - Recovery: LEI > COI > LAG
    - Expansion: COI > LEI > LAG
    - Slowdown: LAG > COI > LEI
    - Recession: LEI < -1.0 AND COI < 0 (Override)
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Setup paths
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


from mie_lib.utils.paths import RAW_DATA_DIR, DATA_DIR, PROCESSED_DATA_DIR

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

MACRO_ANALYSIS_DIR = DATA_DIR / "analytics" / "macro"
MACRO_RAW_DIR = RAW_DATA_DIR / "macro" / "fred"

def load_and_resample(series_id: str) -> pd.Series:
    """Load FRED series and resample to Month-End. Needed for SP500."""
    file_path = MACRO_RAW_DIR / f"{series_id}.parquet"
    if not file_path.exists():
        pass
        
    if not file_path.exists():
        raise FileNotFoundError(f"Series {series_id} not found at {file_path}")
    
    df = pd.read_parquet(file_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    return df['value'].resample('ME').last()

def run_business_cycle_calculation():
    LOG.info("Starting Business Cycle Calculation (Single Source of Truth)...")
    
    # 1. Load Data from Existing Models
    try:
        # Load SP500 for correlation analysis
        s_sp500 = load_and_resample("SP500")

        # Load LEI (Leading)
        # Note: LEI might be in lei_model.parquet OR processed_lei_coi_enhanced.parquet
        # We prefer the consolidated one if available, or the individual.
        # Based on user request: data/analytics/macro/processed_lei_coi_enhanced.parquet (for LEI)
        lei_path = MACRO_ANALYSIS_DIR / "processed_lei_coi_enhanced.parquet"
        if not lei_path.exists():
             raise FileNotFoundError(f"LEI data not found at {lei_path}")
        df_lei_source = pd.read_parquet(lei_path)
        df_lei_source['date'] = pd.to_datetime(df_lei_source['date'])
        df_lei_source = df_lei_source.set_index('date').sort_index()

        # Load COI (Coincident) from the same ENHANCED file to get full history
        # Old source (coi_model.parquet) was truncated to 1996.
        # Enhanced file has COI_Final column starting from 1960s.
        # We reuse df_lei_source because it's the same file.
        df_coi_source = df_lei_source.copy()
        
        LOG.info(f"Using COI from Enhanced File: {len(df_coi_source)} rows")

        # Load LAG (Lagging)
        # User request: data/processed/lag_model.parquet
        lag_path = PROCESSED_DATA_DIR / "lag_model.parquet"
        if not lag_path.exists():
             raise FileNotFoundError(f"LAG data not found at {lag_path}")
        df_lag_source = pd.read_parquet(lag_path)
        if 'date' in df_lag_source.columns:
            df_lag_source['date'] = pd.to_datetime(df_lag_source['date'])
            df_lag_source = df_lag_source.set_index('date')
        df_lag_source = df_lag_source.sort_index()


        LOG.info(f"Loaded Models: LEI={len(df_lei_source)}, COI={len(df_coi_source)}, LAG={len(df_lag_source)}")
        
        LOG.info(f"LEI Index: {df_lei_source.index[0]} to {df_lei_source.index[-1]}")
        LOG.info(f"COI Index: {df_coi_source.index[0]} to {df_coi_source.index[-1]}")
        LOG.info(f"LAG Index: {df_lag_source.index[0]} to {df_lag_source.index[-1]}")
        LOG.info(f"SP500 Index: {s_sp500.index[0]} to {s_sp500.index[-1]}")



        # Ensure indices are timezone-naive
        if df_lei_source.index.tz is not None: df_lei_source.index = df_lei_source.index.tz_localize(None)
        if df_coi_source.index.tz is not None: df_coi_source.index = df_coi_source.index.tz_localize(None)
        if df_lag_source.index.tz is not None: df_lag_source.index = df_lag_source.index.tz_localize(None)
        if s_sp500.index.tz is not None: s_sp500.index = s_sp500.index.tz_localize(None)

        # Resample to Month End to align indices
        df_lei_source = df_lei_source.resample('ME').last()
        df_coi_source = df_coi_source.resample('ME').last()
        df_lag_source = df_lag_source.resample('ME').last()
        s_sp500 = s_sp500.resample('ME').last()

    except Exception as e:
        LOG.error(f"Failed to load data: {e}")
        raise

    # 2. Merge Indicators
    # We need: LEI_Final, COI_Final (from coi_model), LAG_Final (from lag_model)
    
    # Extract Series
    s_lei = df_lei_source['LEI_Final']
    
    # Check column names for COI
    # Enhanced file uses 'COI_Final'
    if 'COI_Final' in df_coi_source.columns:
        s_coi = df_coi_source['COI_Final']
    else:
        # Fallback if somehow using old file (shouldn't happen with above change)
        s_coi = df_coi_source['coi_composite']
    
    # Check column names for LAG
    # lag_model.parquet columns: [lag_composite, signal_line, ...]
    # We use 'lag_composite' as LAG_Final
    s_lag = df_lag_source['lag_composite']

    # Merge
    dfs = [s_lei.rename("LEI_Final"), s_coi.rename("COI_Final"), s_lag.rename("LAG_Final"), s_sp500.rename("SP500_Close")]
    combined = pd.concat(dfs, axis=1)
    
    # Drop rows where any indicator is missing (cannot determine phase)
    # Actually, we might want to keep robust history even if one is missing? 
    # But methodology requires relative ordering. So we need all 3.
    combined = combined.dropna(subset=['LEI_Final', 'COI_Final', 'LAG_Final'])

    
    # 3. Determine Cycle Phase
    def get_phase(row):
        lei = row['LEI_Final']
        coi = row['COI_Final']
        lag = row['LAG_Final']
        
        # Priority 1: Recession definition (Override)
        if lei < -1.0 and coi < 0:
            return "Recession"
            
        # Priority 2: Relative Ordering
        # Recovery: LEI > COI > LAG
        if lei > coi and coi > lag:
            return "Recovery"
            
        # Expansion: COI > LEI > LAG
        if coi > lei and lei > lag:
            return "Expansion"
            
        # Slowdown: LAG > COI > LEI
        if lag > coi and coi > lei:
            return "Slowdown"
            
        # Fallback Logic for mixed states
        if lag >= max(lei, coi):
            return "Slowdown"
        elif lei >= max(coi, lag):
            return "Recovery"
        else:
             return "Expansion"

    combined['Cycle_Phase'] = combined.apply(get_phase, axis=1)
    
    # Recession Prob (Derived from LEI as per previous logic)
    combined['Recession_Prob'] = np.where(combined['LEI_Final'] < -1.0, 0.85, 0.05)
    
    # 4. S&P 500 Correlation Analysis
    sp500_yoy = combined['SP500_Close'].pct_change(12)
    
    best_lag = 0
    best_corr = 0.0
    
    LOG.info("--- Market Lead/Lag Correlations ---")
    for shift_months in [0, 3, 6, 12]:
        lei_shifted = combined['LEI_Final'].shift(shift_months)
        valid_idx = lei_shifted.dropna().index.intersection(sp500_yoy.dropna().index)
        if len(valid_idx) > 20:
            corr = lei_shifted.loc[valid_idx].corr(sp500_yoy.loc[valid_idx])
            LOG.info(f"LEI Lead {shift_months}m Correlation with SP500 YoY: {corr:.3f}")
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = shift_months
    
    LOG.info(f"Optimal Market Lead: LEI leads by {best_lag} months (Corr: {best_corr:.3f})")
    
    # 5. Save
    output_df = combined.reset_index().rename(columns={'index': 'date'})
    output_file = MACRO_ANALYSIS_DIR / "processed_business_cycle.parquet"
    output_df.to_parquet(output_file, index=False)
    
    LOG.info(f"Business Cycle Data saved to {output_file}")
    LOG.info(f"Last Row:\n{output_df.iloc[-1]}")

if __name__ == "__main__":
    run_business_cycle_calculation()
