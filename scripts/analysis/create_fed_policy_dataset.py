#!/usr/bin/env python3
"""
Create Fed Policy Dataset

Fetches Federal Funds Rate from FRED and calculates rate changes
and policy stance classification.

Output: data/outcomes/fed_policy.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Add project to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))

from mie_lib.data_ingest.macro.providers.fred import FredProvider

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "outcomes"
OUTPUT_FILE = OUTPUT_DIR / "fed_policy.parquet"


def calculate_policy_stance(df):
    """
    Classify Fed policy stance based on rate changes.
    
    Logic:
    - Tightening: 3-month change > +25 bps
    - Easing: 3-month change < -25 bps
    - Neutral: abs(3-month change) <= 25 bps
    
    Args:
        df: DataFrame with 'fed_funds_rate' column
        
    Returns:
        DataFrame with policy stance classification
    """
    # Calculate 1-month change in basis points
    df['change_1m_bps'] = (df['fed_funds_rate'] - df['fed_funds_rate'].shift(1)) * 100
    
    # Calculate 3-month change in basis points
    df['change_3m_bps'] = (df['fed_funds_rate'] - df['fed_funds_rate'].shift(3)) * 100
    
    # Classify policy stance
    def classify_stance(change_3m):
        if pd.isna(change_3m):
            return 'neutral'
        elif change_3m > 25:
            return 'tightening'
        elif change_3m < -25:
            return 'easing'
        else:
            return 'neutral'
    
    df['policy_stance'] = df['change_3m_bps'].apply(classify_stance)
    
    return df


def main():
    print("Creating Fed Policy Dataset")
    print("=" * 60)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Fetch Fed Funds Rate from FRED
    print("\n1. Fetching FEDFUNDS from FRED...")
    provider = FredProvider()
    fedfunds_data = provider.fetch_series('FEDFUNDS', start_date=None)
    
    print(f"   Fetched {len(fedfunds_data)} observations")
    print(f"   Period: {fedfunds_data['date'].min()} to {fedfunds_data['date'].max()}")
    
    # Rename columns
    df = fedfunds_data.rename(columns={'value': 'fed_funds_rate'})
    df = df.sort_values('date').reset_index(drop=True)
    
    # Calculate policy stance
    print("\n2. Calculating rate changes and policy stance...")
    df = calculate_policy_stance(df)
    
    # Count stance distribution
    stance_counts = df['policy_stance'].value_counts()
    print(f"   Policy stance distribution:")
    for stance, count in stance_counts.items():
        pct = (count / len(df)) * 100
        print(f"   - {stance}: {count} months ({pct:.1f}%)")
    
    # Summary statistics
    print(f"\n3. Summary statistics:")
    print(f"   Current rate: {df['fed_funds_rate'].iloc[-1]:.2f}%")
    print(f"   Historical avg: {df['fed_funds_rate'].mean():.2f}%")
    print(f"   Historical max: {df['fed_funds_rate'].max():.2f}%")
    print(f"   Historical min: {df['fed_funds_rate'].min():.2f}%")
    
    # Save to parquet
    print(f"\n4. Saving to {OUTPUT_FILE}...")
    df.to_parquet(OUTPUT_FILE, index=False)
    
    print("\n" + "=" * 60)
    print("✅ Fed Policy Dataset created successfully!")
    print(f"   Output: {OUTPUT_FILE}")
    print(f"   Observations: {len(df)}")
    print(f"   Period: {df['date'].min().year} - {df['date'].max().year}")
    print(f"   Columns: {list(df.columns)}")
    
    return df


if __name__ == "__main__":
    df = main()
