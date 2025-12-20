
import pandas as pd
import sys

try:
    df = pd.read_parquet("data/analytics/gex/SPY_profile.parquet")
    print("Columns:", df.columns.tolist())
    if not df.empty:
        print("First row:", df.iloc[0].to_dict())
        
        # Check for non-zero values
        weekly_sum = df['weekly_call_gex'].abs().sum() + df['weekly_put_gex'].abs().sum()
        quarterly_sum = df['quarterly_call_gex'].abs().sum() + df['quarterly_put_gex'].abs().sum()
        
        print(f"Total Weekly GEX Abs Sum: {weekly_sum}")
        print(f"Total Quarterly GEX Abs Sum: {quarterly_sum}")
    else:
        print("DataFrame is empty.")
except Exception as e:
    print(e)
