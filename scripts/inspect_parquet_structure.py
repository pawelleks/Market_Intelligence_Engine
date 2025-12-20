import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def analyze_full_structure(ticker="SPY"):
    logger.info(f"--- Analyzing Data Structure for {ticker} ---")
    
    # 1. Load Price/Features
    feat_path = Path(f"data/features/{ticker}.parquet")
    if not feat_path.exists():
        logger.error(f"Features missing: {feat_path}")
        return
        
    df_feat = pd.read_parquet(feat_path)
    logger.info(f"Loaded Features: {len(df_feat)} rows. Date Range: {df_feat['date'].min()} to {df_feat['date'].max()}")
    
    # 2. Load and Join HMM
    hmm_path = Path(f"data/analytics/hmm/{ticker}/hmm_states.parquet")
    if hmm_path.exists():
        logger.info(f"Loading HMM States: {hmm_path}")
        df_hmm = pd.read_parquet(hmm_path)
        
        # Merge
        # Ensure date types match
        df_feat['date'] = pd.to_datetime(df_feat['date'])
        df_hmm['date'] = pd.to_datetime(df_hmm['date'])
        
        df = pd.merge(df_feat, df_hmm[['date', 'hmm_state']], on='date', how='inner')
        logger.info(f"Merged Data: {len(df)} rows (Intersection).")
        
        # HMM Stats
        logger.info("\n=== 1. HMM Statistical Profile ===")
        # Calculate returns if needed
        if "close" in df.columns and "ret_1d" not in df.columns:
             df['ret_1d'] = df['close'].pct_change()
             
        stats = df.groupby("hmm_state")['ret_1d'].agg(['mean', 'std', 'count'])
        overall_std = df['ret_1d'].std()
        
        labels = {}
        for state, row in stats.iterrows():
            mu = row['mean']
            sigma = row['std']
            
            if mu < -0.0002 and sigma > overall_std:
                label = "Volatile Bear" # Negative mean, high vol
            elif mu > 0.0002 and sigma < overall_std:
                label = "Steady Bull"   # Positive mean, low vol
            elif sigma > overall_std * 1.5:
                label = "High Volatility / Correction"
            else:
                label = "Sideways / Chop"
                
            labels[state] = label
            
        print(f"{'State':<6} | {'Mean Ret':<12} | {'Daily Vol':<12} | {'Count':<6} | {'Proposed Label'}")
        print("-" * 70)
        for state, row in stats.iterrows():
            print(f"{state:<6} | {row['mean']:+.6f}     | {row['std']:.6f}     | {int(row['count']):<6} | {labels.get(state)}")
            
        print("\nProposed HMM_PROFILE_MAP = {")
        for s, l in labels.items():
            print(f"    {s}: \"{l}\",")
        print("}")
        
    else:
        logger.warning("No HMM State file found.")

    # 3. Column Scouting: GEX
    gex_path = Path(f"data/analytics/gex/{ticker}_profile.parquet")
    if gex_path.exists():
        logger.info(f"\n=== 2. Gamma Exposure (GEX) Scouting ===")
        logger.info(f"File: {gex_path}")
        df_gex = pd.read_parquet(gex_path)
        print("Columns found in GEX Profile:")
        for c in df_gex.columns:
            print(f" - {c}")
        # Check if it holds history or just snapshot
        if 'date' in df_gex.columns:
             print(f"Date range: {df_gex['date'].min()} to {df_gex['date'].max()}")
    else:
        logger.warning(f"No GEX profile found at {gex_path}")

    # 4. Column Scouting: Expected Moves
    # Exploring archive for snapshots
    em_dir = Path("data/analytics/expected_moves")
    if em_dir.exists():
         # Basic check of subdirs
         logger.info(f"\n=== 3. Expected Moves Scouting ===")
         # Look for parquet in archive or pending?
         # Or maybe expected_moves.json in analytics root?
         pass # Handled by shell exploration, script focus on Parquet columns
    
if __name__ == "__main__":
    analyze_full_structure("SPY")
