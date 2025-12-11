import pandas as pd
import sys

try:
    print("Pandas version:", pd.__version__)
    path = "data/raw/AAPL.parquet"
    print(f"Reading {path}...")
    df = pd.read_parquet(path)
    print("Success!")
    print(df.head())
    print("Columns:", df.columns)
except Exception as e:
    print("Failed to read parquet:", e)
    # Check dependencies
    try:
        import pyarrow
        print("Pyarrow version:", pyarrow.__version__)
    except ImportError:
        print("Pyarrow not installed.")
    try:
        import fastparquet
        print("Fastparquet version:", fastparquet.__version__)
    except ImportError:
        print("Fastparquet not installed.")
