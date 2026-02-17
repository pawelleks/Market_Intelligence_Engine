import pandas as pd
from pathlib import Path
from mie_lib.analytics.expected_moves.models import HistoricalEMRecord
from mie_lib.utils.paths import OPTIONS_DIR
import json

def test_history_validation():
    path = OPTIONS_DIR / "spy_expected_moves.parquet"
    if not path.exists():
        print("File not found")
        return

    df = pd.read_parquet(path)
    
    # Filter for SPY
    df = df[df["ticker"] == "SPY"]
    
    # Handle NaN
    df = df.where(pd.notnull(df), None)
    
    records = df.to_dict(orient="records")
    print(f"Found {len(records)} records for SPY")
    
    if len(records) > 0:
        print("Sample record keys:", records[0].keys())
        print("Sample record:", records[0])
        
        try:
            # Validate first record
            HistoricalEMRecord(**records[0])
            print("Validation Successful for first record")
        except Exception as e:
            print("Validation Failed for first record:")
            print(e)
            
        # Validate all
        valid_count = 0
        for r in records:
            try:
                HistoricalEMRecord(**r)
                valid_count += 1
            except:
                pass
        print(f"Successfully validated {valid_count}/{len(records)} records")

if __name__ == "__main__":
    test_history_validation()
