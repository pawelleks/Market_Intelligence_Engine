import pandas as pd
import numpy as np
from mie_lib.analytics.downtrend_engine import compute_downtrend_signals_historical
from mie_lib.data_ingest.data_aligner import fetch_and_align_dcs_assets

try:
    print("Fetching real data (30 years)...")
    df_aligned, weights = fetch_and_align_dcs_assets('SPY', lookback_days=30*365)
    print(f"Data fetched. Shape: {df_aligned.shape}")
    
    print("Computing signals...")
    results = compute_downtrend_signals_historical(df_aligned, weights=weights, ticker='SPY')
    print("Success!")
    print(results[0])
except Exception as e:
    import traceback
    traceback.print_exc()
