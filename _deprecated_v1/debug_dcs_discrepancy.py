
import pandas as pd
import sys
import os
from datetime import date
from pprint import pprint

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

try:
    from mie_lib.analytics.downtrend_engine import compute_downtrend_score_latest, compute_downtrend_signals_historical
    from mie_lib.data_ingest.data_aligner import fetch_and_align_dcs_assets
    
    ticker = "SPY"
    print(f"--- Debugging DCS for {ticker} ---")
    
    # 1. Run Latest Logic
    print("\n[Latest Logic]")
    # Internally calls fetch_and_align(lookback=500)
    df_latest_aligned, _ = fetch_and_align_dcs_assets(ticker, lookback_days=500)
    if not df_latest_aligned.empty:
        print(f"Latest Aligned DF End: {df_latest_aligned.index[-1]}")
        latest_res = compute_downtrend_score_latest(df_latest_aligned, ticker=ticker)
        print(f"Latest Score: {latest_res['latest_score_100']}")
        print(f"Check Date: {latest_res['check_date']}")
    else:
        print("Latest aligned df empty.")

    # 2. Run Historical Logic
    print("\n[Historical Logic]")
    # Internally calls fetch_and_align(lookback=10950)
    df_hist_aligned, _ = fetch_and_align_dcs_assets(ticker, lookback_days=10950)
    
    if not df_hist_aligned.empty:
        print(f"Historical Aligned DF End: {df_hist_aligned.index[-1]}")
        hist_res = compute_downtrend_signals_historical(df_hist_aligned, ticker=ticker)
        
        # Show last 5 records
        print("\nLast 5 Historical Records:")
        for r in hist_res[-5:]:
            print(f"Date: {r['date']}, Score: {r['score']:.2f}")
    else:
        print("Historical aligned df empty.")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
