import pandas as pd
import sys
from pathlib import Path

def check_flip():
    path = Path("data/analytics/gex/SPY_profile.parquet")
    if not path.exists():
        print(f"File not found: {path}")
        return

    df = pd.read_parquet(path)
    print(f"Loaded {len(df)} rows.")
    
    # Sort just in case (though parquet usually preserves, logic depends on it)
    df = df.sort_values("strike")
    
    prev_net = 0
    found = False
    flip_strike = None
    
    print("\n--- Scanning for Flip ---")
    for index, row in df.iterrows():
        strike = row['strike']
        net = row['total_net_gex']
        
        # Simple logging around 0
        if abs(net) < 1000000: # Log small values
             pass
             
        if prev_net != 0:
            # Check crossing
            if (prev_net < 0 and net >= 0) or (prev_net > 0 and net <= 0):
                print(f"FLIP FOUND at Strike {strike}!")
                print(f"Prev: {prev_net}, Curr: {net}")
                
        prev_net = net

    if not found:
        print("NO FLIP FOUND.")
        print(f"Min Net: {df['total_net_gex'].min()}")
        print(f"Max Net: {df['total_net_gex'].max()}")
        
        # Print a sample to see if it's all negative
        print("\nHead:")
        print(df[['strike', 'total_net_gex']].head())
        print("\nTail:")
        print(df[['strike', 'total_net_gex']].tail())

if __name__ == "__main__":
    check_flip()
