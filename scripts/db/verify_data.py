import pandas as pd
from pathlib import Path

file_path = Path("data/processed/jpm_dashboard/housing.parquet")
if not file_path.exists():
    print(f"File not found: {file_path}")
    exit(1)

df = pd.read_parquet(file_path)
print(f"Columns in {file_path}:")
print(df.columns.tolist())

required_series = ['MORTGAGE30US', 'PERMIT', 'MSACSR', 'CSUSHPISA']
missing = [s for s in required_series if s not in df.columns]

if missing:
    print(f"MISSING SERIES: {missing}")
else:
    print("ALL SERIES PRESENT")

print("Head of new series:")
print(df[required_series].tail())
