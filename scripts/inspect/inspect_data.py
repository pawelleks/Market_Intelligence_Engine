import pandas as pd
import os

print("--- Inspecting SPY GEX Profile Parquet ---")
try:
    df_profile = pd.read_parquet("data/analytics/gex/SPY_profile.parquet")
    print("Columns:", df_profile.columns.tolist())
    print(df_profile.head())
except Exception as e:
    print(f"Error reading profile parquet: {e}")

print("\n--- Inspecting Raw Massive CSV (if available) ---")
raw_dir = "data/raw/massive/options"
found_csv = False
for root, dirs, files in os.walk(raw_dir):
    for file in files:
        if file.endswith(".csv"):
            print(f"Found CSV: {os.path.join(root, file)}")
            try:
                # Read just header and first row
                df_raw = pd.read_csv(os.path.join(root, file), nrows=1)
                print("Raw CSV Columns:", df_raw.columns.tolist())
                found_csv = True
                break
            except Exception as e:
                print(f"Error reading CSV: {e}")
    if found_csv:
        break

if not found_csv:
    print("No Raw CSV found in data/raw/massive/options")
