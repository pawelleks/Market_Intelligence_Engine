import json
import logging
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any

from mie_lib.analytics.minervini import run_minervini_template


logger = logging.getLogger(__name__)

SCANNER_DATA_DIR = Path("data/analytics/scanner")
SCANNER_DATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = SCANNER_DATA_DIR / "minervini_history.parquet"
SNAPSHOT_FILE = SCANNER_DATA_DIR / "minervini_latest.json"

def build_minervini_snapshot(tickers: List[str], target_date: date):
    """
    Scans the provided tickers for Minervini Trend Template criteria.
    Saves daily snapshot to JSON and appends results to Parquet history.
    """
    logger.info(f"Starting Minervini Scanner build for {len(tickers)} tickers on {target_date}...")
    
    results = []
    
    for ticker in tickers:
        try:
            # 1. Use Existing History (update-raw runs before this)
            raw_path = Path(f"data/raw/{ticker}.parquet")
            if not raw_path.exists():
                logger.warning(f"Skipping {ticker}: Parquet file missing (run update-raw first).")
                continue
                
            df = pd.read_parquet(raw_path)

            if df.empty:
                logger.warning(f"Skipping {ticker}: DataFrame empty.")
                continue
                
            # 2. Run Analysis
            # run_minervini_template handles the SMA calc and date slicing internally
            # It expects a DF with 'Date', 'Close', etc.
            analysis = run_minervini_template(df, target_date)
            
            # 3. Flatten Result for Table/Storage
            checks = analysis.get("data_status", {})
            row = {
                "date": target_date.isoformat(),
                "ticker": ticker,
                "current_price": analysis.get("current_price"),
                "status": analysis.get("status"), # PASS/FAIL
                "total_score": analysis.get("total_passed"),
                "required_score": analysis.get("required_passes"),
                # Core Signals
                "price_gt_smas": checks.get("P_GT_MA"),
                "sma150_gt_sma200": checks.get("MA_150_GT_200"),
                "sma200_trending": checks.get("MA_200_RISING"),
                "sma50_gt_sma150": checks.get("MA_50_GT_LONG"),
                "price_gt_sma50": checks.get("P_GT_MA_50"),
                "price_gt_52w_low_25": checks.get("FAR_FROM_LOW"), 
                "price_near_52w_high_25": checks.get("CLOSE_TO_HIGH"),
                 # We can add explicit values for display if needed, but for now booleans are key
            }
            results.append(row)
            
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")
            
    if not results:
        logger.warning("No results generated.")
        return 0
        
    df_results = pd.DataFrame(results)
    
    # 4. Save Latest Snapshot (JSON)
    # This is what the Frontend will consume
    snapshot_data = {
        "date": target_date.isoformat(),
        "timestamp": datetime.now().isoformat(),
        "count": len(results),
        "data": df_results.to_dict(orient="records")
    }
    
    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(snapshot_data, f, indent=2)
    logger.info(f"Saved snapshot to {SNAPSHOT_FILE}")
    
    # 5. Append to History (Parquet)
    if HISTORY_FILE.exists():
        try:
            df_hist = pd.read_parquet(HISTORY_FILE)
            # Remove existing data for this date to avoid duplicates (idempotency)
            df_hist = df_hist[df_hist['date'] != target_date.isoformat()]
            df_combined = pd.concat([df_hist, df_results], ignore_index=True)
        except Exception as e:
            logger.error(f"Error reading history, overwriting: {e}")
            df_combined = df_results
    else:
        df_combined = df_results
        
    df_combined.to_parquet(HISTORY_FILE, index=False)
    logger.info(f"Updated history in {HISTORY_FILE} (Total rows: {len(df_combined)})")
    
    return len(results)
