
import pandas as pd
import json
import os

GEX_DIR = "data/analytics/gex"
OPT_DIR = "data/analytics/options"
SPY_PROFILE = os.path.join(GEX_DIR, "SPY_profile.parquet")
SPY_GEX_JSON = os.path.join(GEX_DIR, "SPY_gex.json")
SPY_EXP_MOVES = os.path.join(OPT_DIR, "spy_expected_moves.parquet")

def inspect_parquet(path):
    print(f"\n--- Inspecting {path} ---")
    if not os.path.exists(path):
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    print("Columns:", df.columns.tolist())
    print("\nData Types:")
    print(df.dtypes)
    
    print("\nSample Data (First 5 rows):")
    print(df.head().to_string())
    
    print("\nDescribe Strike Granularity:")
    if 'strike' in df.columns:
        strikes = sorted(df['strike'].unique())
        diffs = pd.Series(strikes).diff().value_counts().head()
        print("Strike Differences (Top 5):")
        print(diffs)
        
    print("\nExpiration Dates Available:")
    if 'expiry_date' in df.columns:
        print(sorted(df['expiry_date'].unique()))
    elif 'date' in df.columns and 'expiry' in df.columns:
         print(sorted(df['expiry'].unique()))
    elif 'date' in df.columns: 
        print("Date column found (might be snapshot date):", df['date'].unique())

def inspect_json(path):
    print(f"\n--- Inspecting {path} ---")
    if not os.path.exists(path):
        print("File not found.")
        return

    with open(path, 'r') as f:
        data = json.load(f)
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    inspect_json(SPY_GEX_JSON)
    inspect_parquet(SPY_PROFILE)
    inspect_parquet(SPY_EXP_MOVES)
