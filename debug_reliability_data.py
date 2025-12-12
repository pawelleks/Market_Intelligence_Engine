import pandas as pd
from pathlib import Path

path = Path("data/analytics/options/spy_expected_moves.parquet")

if not path.exists():
    print(f"File not found: {path}")
else:
    try:
        df = pd.read_parquet(path)
        print(f"--- {path.name} ---")
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print("\nFirst 5 rows:")
        print(df.head())
        
        if "closed_within_em" in df.columns:
            print(f"\nclosed_within_em counts:\n{df['closed_within_em'].value_counts(dropna=False)}")
        else:
            print("\nCOLUMN 'closed_within_em' MISSING!")
            
    except Exception as e:
        print(f"Error reading {path}: {e}")
