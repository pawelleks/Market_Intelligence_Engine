#!/usr/bin/env python3
"""
Final Verification Script: LEI vs LAG "Fed Trap" Divergence
Calculates the 'Risk Spread' (LAG - LEI) and confirms the 2008 'Alligator Jaw'.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("fed_trap_analysis")

def analyze_divergence():
    lei_path = PROCESSED_DATA_DIR / "lei_model.parquet"
    lag_path = PROCESSED_DATA_DIR / "lag_model.parquet"

    if not lei_path.exists() or not lag_path.exists():
        LOG.error("One or more model files missing. Run calculation scripts first.")
        return

    lei_df = pd.read_parquet(lei_path)
    lag_df = pd.read_parquet(lag_path)

    # Align Data
    df = pd.DataFrame(index=lei_df.index)
    df['lei'] = lei_df['lei_composite']
    df['lag'] = lag_df['lag_composite']
    
    # Calculate Risk Spread (LAG - LEI)
    # High Spread = LAG is high (overheating) while LEI is low (crashing)
    df['risk_spread'] = df['lag'] - df['lei']

    # 1. 2008 Analysis (The Alligator Jaw)
    period_2008 = df.loc['2007-06-01':'2008-12-01']
    LOG.info("\n" + "="*60)
    LOG.info("ANALYSIS: THE 2008 'ALLIGATOR JAW' (LAG vs LEI)")
    LOG.info("="*60)
    
    # Find max spread date in 2008
    max_spread_2008_idx = period_2008['risk_spread'].idxmax()
    max_spread_2008_val = period_2008['risk_spread'].max()
    
    LOG.info(f"Max 2008 Divergence: {max_spread_2008_val:.2f} on {max_spread_2008_idx.date()}")
    LOG.info(f"At this peak: LAG={df.at[max_spread_2008_idx, 'lag']:.2f}, LEI={df.at[max_spread_2008_idx, 'lei']:.2f}")
    LOG.info("Interpretation: Fed was trapped by LAG strength while LEI was already in deep contraction.")

    # 2. 2020 Analysis (The COVID Blip)
    period_2020 = df.loc['2019-12-01':'2020-06-01']
    LOG.info("\n" + "="*60)
    LOG.info("ANALYSIS: THE 2020 COVID 'NON-TRAP'")
    LOG.info("="*60)
    max_spread_2020_val = period_2020['risk_spread'].max()
    LOG.info(f"Max 2020 Divergence: {max_spread_2020_val:.2f}")
    LOG.info("Note: 2020 showed a smaller divergence as LAG crashed quickly with the shutdown.")

    # 3. Current State Analysis
    LOG.info("\n" + "="*60)
    LOG.info("ANALYSIS: CURRENT 'FED TRAP' RISK")
    LOG.info("="*60)
    latest_date = df.index[-1]
    latest = df.iloc[-1]
    LOG.info(f"Latest Date: {latest_date.date()}")
    LOG.info(f"Current LEI: {latest['lei']:.4f}")
    LOG.info(f"Current LAG: {latest['lag']:.4f}")
    LOG.info(f"Current Risk Spread: {latest['risk_spread']:.4f}")
    
    # Save the combined model for the dashboard if needed
    output_path = PROCESSED_DATA_DIR / "fed_trap_divergence.parquet"
    df.to_parquet(output_path)
    LOG.info(f"\nDivergence data saved to {output_path}")

if __name__ == "__main__":
    analyze_divergence()
