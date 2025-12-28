
import logging
import sys
import pandas as pd
from mie_lib.analytics.gex.gex_pipeline import _fetch_yfinance_chain_df, run_gex_pipeline_parallel
from mie_lib.analytics.hmm.hmm_pipeline import run_backtest_hmm_parallel

logging.basicConfig(level=logging.INFO)

def verify_gex_fetch():
    print("--- Verifying GEX Hybrid Fetch ---")
    ticker = "SPY"
    print(f"Fetching chain for {ticker}...")
    df = _fetch_yfinance_chain_df(ticker)
    
    if df.empty:
        print("FAILED: Returned empty DataFrame")
        return
        
    print(f"SUCCESS: Fetched {len(df)} contracts.")
    print("Columns:", df.columns.tolist())
    print("Sample:\n", df.head())
    
    # Check for required columns
    required = {'contractSymbol', 'oi', 'iv', 'strike', 'expiration', 'option_type'}
    missing = required - set(df.columns)
    if missing:
        print(f"FAILED: Missing columns: {missing}")
    else:
        print("SUCCESS: All required columns present.")

def verify_hmm_syntax():
    print("\n--- Verifying HMM Parsing ---")
    # Just import checks done by loading module above
    print("HMM Module loaded successfully.")
    
if __name__ == "__main__":
    verify_gex_fetch()
    verify_hmm_syntax()
