import os
import logging
from datetime import datetime
from pathlib import Path
from mie_lib.analytics.skew.skew_pipeline import run_skew_pipeline_parallel

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

def backfill_skew():
    data_dir = Path("data/raw/massive/options")
    if not data_dir.exists():
        print(f"Directory {data_dir} not found.")
        return

    # Find all options_YYYY-MM-DD.csv files
    files = list(data_dir.glob("options_*.csv"))
    dates = []
    for f in files:
        # Extract date from options_YYYY-MM-DD.csv
        try:
            date_str = f.stem.replace("options_", "")
            dates.append(date_str)
        except:
            continue
    
    dates.sort()
    print(f"Found {len(dates)} dates to backfill: {dates}")

    # Core tickers for dashboard
    tickers = ["SPY", "QQQ", "IWM", "DIA"]

    for d_str in dates:
        print(f"=== Backfilling {d_str} ===")
        # Note: we use parallel pipeline which handles storage internally
        try:
            run_skew_pipeline_parallel(tickers=tickers, target_date=d_str)
        except Exception as e:
            print(f"Failed {d_str}: {e}")

if __name__ == "__main__":
    backfill_skew()
