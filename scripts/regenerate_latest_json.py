import pandas as pd
import json
import os
import glob
from datetime import datetime

DATA_DIR = "/app/data/analytics/options"
OUTPUT_FILE = os.path.join(DATA_DIR, "latest.json")

def process():
    if not os.path.exists(DATA_DIR):
        print(f"Data dir not found: {DATA_DIR}")
        return

    parquet_files = glob.glob(os.path.join(DATA_DIR, "*_expected_moves.parquet"))
    print(f"Found {len(parquet_files)} parquet files.")

    tickers_data = {}
    global_as_of = ""
    global_vix = 0.0

    for pq_file in parquet_files:
        try:
            ticker_raw = os.path.basename(pq_file).replace("_expected_moves.parquet", "").upper()
            df = pd.read_parquet(pq_file)
            if df.empty:
                continue
                
            # Ensure date column is datetime (or string that sorts correctly)
            if "date" in df.columns:
                 # Check if date is string or object, convert if needed for sorting?
                 # Parquet usually preserves types. Let's assume it sorts.
                 df = df.sort_values("date")
            else:
                 print(f"Skipping {ticker_raw}: no date column")
                 continue
                 
            last_date = df.iloc[-1]["date"]
            
            # Get all rows for the last date
            last_rows = df[df["date"] == last_date]
            
            if last_rows.empty:
                continue

            # Construct Ticker Data
            ref_row = last_rows.iloc[0]
            
            # Track latest global date
            if not global_as_of or str(last_date) > global_as_of:
                global_as_of = str(last_date)
                if "vix1d" in ref_row:
                    global_vix = float(ref_row["vix1d"])

            t_data = {
                "spot_price": float(ref_row["spot_price"]),
                "vix1d": float(ref_row["vix1d"]) if "vix1d" in ref_row else 0.0,
                "timestamp": datetime.now().isoformat(),
                "source": "ParquetRebuild",
                "expirations": {}
            }

            for _, row in last_rows.iterrows():
                exp_type = row["expiry_type"] # ODTE, WEEKLY, MONTHLY
                
                # Basic validation
                em_val = row["expected_move"]
                if pd.isna(em_val): em_val = 0.0
                
                exp_data = {
                    "expiry_date": str(row["expiry_date"]),
                    "days_to_expiry": 0,
                     "em_dollars": float(em_val),
                     "upper_range": float(row["upper_range"]) if not pd.isna(row["upper_range"]) else 0.0,
                     "lower_range": float(row["lower_range"]) if not pd.isna(row["lower_range"]) else 0.0,
                     "em_iv": float(row.get("em_iv", 0.0)) if not pd.isna(row.get("em_iv")) else 0.0
                }
                
                # Add debug if available (optional)
                
                t_data["expirations"][exp_type] = exp_data
            
            tickers_data[ticker_raw] = t_data
            
        except Exception as e:
            print(f"Error processing {pq_file}: {e}")

    # Build Final JSON structure
    final_output = {
        "as_of": global_as_of,
        "source": "RegeneratedFromParquet",
        "vix1d": global_vix,
        "confidence_score": 80, 
        "tickers": tickers_data
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_output, f, indent=2)
    
    print(f"Successfully regenerated latest.json with {len(tickers_data)} tickers. As Of: {global_as_of}")

if __name__ == "__main__":
    process()
