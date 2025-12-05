import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path
import logging
import json

from mie_lib.analytics.expected_moves.models import HistoricalEMRecord, RealizedOHLC
from mie_lib.utils.paths import OPTIONS_DIR

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YFinanceClient:
    """
    Client for fetching EOD OHLC data from Yahoo Finance.
    """
    def get_eod_ohlc(self, ticker: str, expiration_date: date) -> Optional[RealizedOHLC]:
        """
        Fetches EOD OHLC data for a specific date.
        Returns None if data is not available.
        """
        try:
            # yfinance history expects start (inclusive) and end (exclusive)
            # To get data for expiration_date, we ask for start=expiration_date, end=expiration_date + 1 day
            start_date = expiration_date
            end_date = expiration_date + timedelta(days=1)
            
            # If expiration is today, and market is closed, yfinance might return it.
            # If market is open, it returns live/delayed data which is fine for "current" status,
            # but for "reliability" we ideally want finalized close.
            # However, for the purpose of "is it currently within range", live close is acceptable.
            
            # Optimization: If date is in future, return None immediately
            if start_date > date.today():
                return None
                
            t = yf.Ticker(ticker)
            hist = t.history(start=start_date, end=end_date, interval="1d")
            
            if hist.empty:
                return None
                
            # Get the first row (should be the only one)
            row = hist.iloc[0]
            
            return RealizedOHLC(
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"])
            )
        except Exception as e:
            logger.warning(f"Failed to fetch OHLC for {ticker} on {expiration_date}: {e}")
            return None

def calculate_reliability_metrics(record: dict, ohlc: RealizedOHLC) -> dict:
    """
    Calculates the reliability metrics and updates the record dict.
    """
    # 1. Closed Within EM
    # Ensure ranges are floats
    lower = float(record["lower_range"])
    upper = float(record["upper_range"])
    em_dollars = float(record["expected_move"]) if "expected_move" in record else float(record.get("expected_move_dollars", 0.0))
    
    record["closed_within_em"] = (ohlc.close >= lower) and (ohlc.close <= upper)
    
    # 2. High Breach
    high_breach = max(0.0, ohlc.high - upper)
    record["high_breach_amount"] = high_breach
    if em_dollars > 0:
        record["high_breach_percent"] = (high_breach / em_dollars) * 100.0
    else:
        record["high_breach_percent"] = 0.0
        
    # 3. Low Breach
    low_breach = max(0.0, lower - ohlc.low)
    record["low_breach_amount"] = low_breach
    if em_dollars > 0:
        record["low_breach_percent"] = (low_breach / em_dollars) * 100.0
    else:
        record["low_breach_percent"] = 0.0
        
    # Attach the realized OHLC as a dict or flattened columns
    # For parquet storage, flattened columns are often easier, but models.py uses a nested object.
    # However, pandas to_parquet handles dicts/objects if we are careful.
    # But to be safe and queryable, let's flatten or store as JSON string if needed.
    # Actually, the API endpoint reads it. If we store as columns "realized_close", etc., we need to update API to read them.
    # Let's stick to adding columns: realized_close, realized_high, realized_low, realized_open.
    record["realized_close"] = ohlc.close
    record["realized_high"] = ohlc.high
    record["realized_low"] = ohlc.low
    record["realized_open"] = ohlc.open
    
    return record

def process_reliability():
    """
    Main function to process reliability for ALL tickers in the history folder.
    """
    client = YFinanceClient()
    
    # Ensure directory exists
    if not OPTIONS_DIR.exists():
        logger.warning(f"Options directory {OPTIONS_DIR} does not exist.")
        return

    # Scan all *_expected_moves.parquet files
    files = list(OPTIONS_DIR.glob("*_expected_moves.parquet"))
    if not files:
        logger.info("No Expected Moves history files found.")
        return

    total_updated = 0
    
    for file_path in files:
        try:
            logger.info(f"Processing {file_path.name}...")
            df = pd.read_parquet(file_path)
            
            if df.empty:
                continue
                
            # Ensure date columns are date objects
            if "expiry_date" in df.columns:
                df["expiry_date"] = pd.to_datetime(df["expiry_date"]).dt.date
            
            # Identify rows that need processing:
            # 1. Expiry date <= Today
            # 2. Missing realized data (e.g. 'closed_within_em' is NaN or 'realized_close' is NaN)
            
            # Check if columns exist, create if not
            cols_to_check = ["closed_within_em", "realized_close", "high_breach_amount", "high_breach_percent", "low_breach_amount", "low_breach_percent"]
            for col in cols_to_check:
                if col not in df.columns:
                    df[col] = None
            
            # Filter for rows to update
            # We use a mask
            today = date.today()
            
            # Mask: Expiry <= Today AND (closed_within_em is Null)
            mask = (df["expiry_date"] <= today) & (df["closed_within_em"].isna())
            
            indices_to_update = df[mask].index
            
            if len(indices_to_update) == 0:
                logger.info(f"  No pending expired records for {file_path.name}")
                continue
                
            logger.info(f"  Found {len(indices_to_update)} records to update in {file_path.name}")
            
            updated_count = 0
            
            for idx in indices_to_update:
                row = df.loc[idx].to_dict()
                ticker = row.get("ticker")
                # If ticker is missing in row (older schema?), infer from filename
                if not ticker:
                    ticker = file_path.name.replace("_expected_moves.parquet", "").upper()
                
                expiry_date = row["expiry_date"]
                
                # Fetch OHLC
                ohlc = client.get_eod_ohlc(ticker, expiry_date)
                
                if ohlc:
                    # Calculate metrics
                    updated_row = calculate_reliability_metrics(row, ohlc)
                    
                    # Update DataFrame
                    # We update specific columns
                    for k, v in updated_row.items():
                        if k in df.columns:
                            df.at[idx, k] = v
                        else:
                            # Add new column if needed (though we initialized them above)
                            df.at[idx, k] = v
                            
                    updated_count += 1
                else:
                    logger.debug(f"  Could not fetch data for {ticker} on {expiry_date}")
            
            if updated_count > 0:
                # Save back to parquet
                df.to_parquet(file_path, index=False)
                logger.info(f"  Updated {updated_count} records in {file_path.name}")
                total_updated += updated_count
            else:
                logger.info(f"  No records updated for {file_path.name} (data unavailable)")
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"Reliability processing complete. Total updated: {total_updated}")

if __name__ == "__main__":
    process_reliability()
