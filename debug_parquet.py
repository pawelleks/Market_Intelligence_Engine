import pandas as pd
from pathlib import Path

path = Path("data/analytics/options/spy_expected_moves.parquet")
if path.exists():
    df = pd.read_parquet(path)
    print("Columns:", df.columns)
    print("First 5 rows:")
    print(df.head())
    print("\nUnique Tickers:", df["ticker"].unique())
    print("Unique Expiry Types:", df["expiry_type"].unique())
else:
    print(f"File not found: {path}")
