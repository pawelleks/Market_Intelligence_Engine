import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

try:
    df = pd.read_parquet("data/tsmom/tsmom_current.parquet")
    print("--- SNAPSHOT ---")
    print(df.head())
    print("\nDTD/Schema:")
    print(df.dtypes)
except Exception as e:
    print(f"Error reading snapshot: {e}")

print("\n")
try:
    df_sig = pd.read_parquet("data/tsmom/tsmom_signals.parquet")
    if df_sig.empty:
        print("--- NO SIGNALS YET ---")
    else:
        print("--- SIGNALS ---")
        print(df_sig.head())
except Exception as e:
    print(f"Signals file not found or empty: {e}")
