
import sys
import pandas as pd
from pathlib import Path
import logging

# Set up paths
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.mie_lib.data_ingest.macro.providers.fred import FredProvider

# Setup simplistic logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("diagnostic")

def check_abct_dates():
    LOG.info("Starting ABCT Data Diagnostics...")
    
    # Series suspected of causing the 2022 cutoff
    tickers = [
        'PITGCG01USM661N', # PPI Capital Goods
        'CPIAUCSL',        # CPI
        'M2SL',            # M2
        'PSAVERT',         # Savings Rate
        'DGS10',           # 10Y Yield
        'FEDFUNDS',        # Fed Funds
        'GDPC1',           # Real GDP
        'TOTLL',           # Total Loans
        'PMSAVE'           # Personal Saving Amount
    ]
    
    provider = FredProvider()
    
    print(f"{'Ticker':<20} | {'Max Date':<15} | {'Records':<10}")
    print("-" * 50)
    
    cutoff_found = False
    
    for ticker in tickers:
        df = provider.fetch_series(ticker)
        if df.empty:
            print(f"{ticker:<20} | {'NO DATA':<15} | 0")
            continue
            
        max_date = df['date'].max()
        count = len(df)
        
        # Check if max date is outdated (e.g. before 2024)
        is_stale = max_date.year < 2024
        
        # Format for display
        date_str = max_date.strftime('%Y-%m-%d')
        
        # Print with visual alert if stale
        prefix = "🔴" if is_stale else "🟢"
        print(f"{prefix} {ticker:<18} | {date_str:<15} | {count:<10}")
        
        if is_stale:
            cutoff_found = True
            
    if cutoff_found:
        print("\nPossible Culprit Identified: Look for Red (🔴) series.")
    else:
        print("\nAll series appear up to date. The issue might be in the merge/dropna logic.")

if __name__ == "__main__":
    check_abct_dates()
