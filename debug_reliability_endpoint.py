import sys
from pathlib import Path
import pandas as pd
import logging

# Setup mocking for relative imports if running as script from root
sys.path.append("src")

from mie_lib.utils.paths import OPTIONS_DIR

print(f"OPTIONS_DIR resolves to: {OPTIONS_DIR.absolute()}")
print(f"Exists? {OPTIONS_DIR.exists()}")

files = list(OPTIONS_DIR.glob("*_expected_moves.parquet"))
print(f"Found {len(files)} parquet files.")

if not files:
    print("No files found!")
    sys.exit(0)

dfs = []
for f in files:
    try:
        print(f"Reading {f.name}...")
        df = pd.read_parquet(f)
        print(f"  Rows: {len(df)}")
        dfs.append(df)
    except Exception as e:
        print(f"  ERROR: {e}")

if not dfs:
    print("No DataFrames loaded.")
    sys.exit(0)

combined = pd.concat(dfs, ignore_index=True)
print(f"Total Combined Rows: {len(combined)}")

# Replicate Summary Logic
summary = []
grouped = combined.groupby(["ticker", "expiry_type"])
print(f"Groups found: {len(grouped)}")

for (ticker, expiry_type), group in grouped:
    # Filter out pending records
    finalized = group[group["closed_within_em"].notna()]
    print(f"  {ticker} - {expiry_type}: Total {len(group)}, Finalized {len(finalized)}")
    
    if len(finalized) > 0:
        summary.append({
            "ticker": ticker,
            "expiry_type": expiry_type,
            "count": len(finalized)
        })

print(f"Final Summary contains {len(summary)} items.")
print(summary)
