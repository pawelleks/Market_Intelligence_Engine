from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import pandas as pd
from pathlib import Path
import logging

from mie_lib.analytics.expected_moves.models import HistoricalEMRecord

# Setup Router
router = APIRouter(prefix="/api/v1/expected_moves", tags=["Expected Moves"])

from mie_lib.utils.paths import OPTIONS_DIR

# Constants (should match processor)
ARCHIVE_DATA_DIR = OPTIONS_DIR
logger = logging.getLogger(__name__)

def _load_archive_data() -> pd.DataFrame:
    """Helper to load all archived Parquet files into a single DataFrame."""
    if not ARCHIVE_DATA_DIR.exists():
        return pd.DataFrame()
    
    files = list(ARCHIVE_DATA_DIR.glob("*_expected_moves.parquet"))
    if not files:
        return pd.DataFrame()
        
    dfs = []
    for f in files:
        try:
            df_temp = pd.read_parquet(f)
            # Fix: Inject ticker if missing (inferred from filename)
            if "ticker" not in df_temp.columns:
                # filename assumption: {ticker}_expected_moves.parquet
                ticker_derived = f.name.replace("_expected_moves.parquet", "").upper()
                df_temp["ticker"] = ticker_derived
                
            dfs.append(df_temp)
        except Exception as e:
            logger.error(f"Failed to read archive file {f}: {e}")
            print(f"Failed to read archive file {f}: {e}")
            
    if not dfs:
        print("No dataframes loaded.")
        return pd.DataFrame()
        
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total rows loaded: {len(combined)}")
    return combined

@router.get("/reliability/summary")
def get_reliability_summary():
    """
    Returns aggregated reliability statistics grouped by ticker and expiry type.
    """
    df = _load_archive_data()
    
    if df.empty:
        return []
        
    # Ensure required columns exist (handle potential schema evolution or empty files)
    required_cols = ["ticker", "expiry_type", "closed_within_em", "high_breach_amount", "high_breach_percent", "low_breach_percent"]
    if not all(col in df.columns for col in required_cols):
        # If columns missing (e.g. no expired records yet), return empty
        return []

    # Group by Ticker and Expiry Type
    summary = []
    grouped = df.groupby(["ticker", "expiry_type"])
    
    for (ticker, expiry_type), group in grouped:
        # Filter out pending records (where closed_within_em is None)
        # We only want to summarize finalized records
        group = group[group["closed_within_em"].notna()]
        
        total_count = len(group)
        if total_count == 0:
            continue
            
        # Hit Rate: % of closed_within_em == True
        hit_count = group["closed_within_em"].sum()
        hit_rate = (hit_count / total_count) * 100.0
        
        # Average Miss (High + Low Breach Amounts)
        # Note: For any given record, usually only one is > 0, or both 0.
        avg_miss = (group["high_breach_amount"] + group["low_breach_amount"]).mean()
        
        # Max Breach % (Max of High% and Low%)
        max_high_pct = group["high_breach_percent"].max()
        max_low_pct = group["low_breach_percent"].max()
        max_breach_pct = max(max_high_pct, max_low_pct)
        
        summary.append({
            "ticker": ticker,
            "expiry_type": expiry_type,
            "total_records": int(total_count),
            "hit_rate_percent": float(round(hit_rate, 2)),
            "average_high_breach_dollars": float(round(avg_miss, 2)),
            "max_breach_percent": float(round(max_breach_pct, 2))
        })
        
    return summary

@router.get("/reliability/history", response_model=List[HistoricalEMRecord])
def get_reliability_history(
    ticker: Optional[str] = None,
    expiry_type: Optional[str] = None
):
    """
    Returns raw historical EM records with optional filtering.
    """
    df = _load_archive_data()
    
    if df.empty:
        return []
        
    # Apply Filters
    if ticker:
        df = df[df["ticker"] == ticker.upper()]
        
    if expiry_type:
        df = df[df["expiry_type"] == expiry_type.upper()]
        
    # Handle NaN values for JSON serialization (Pandas uses NaN, JSON needs null)
    # Pydantic handles this if we convert to dicts, but let's be safe
    # Actually, Pydantic v2 is strict, v1 allows it. 
    # Best to replace NaN with None before converting to dicts
    # Rename columns to match Pydantic Model
    rename_map = {
        "spot_price": "underlying_price",
        "expected_move": "expected_move_dollars",
        "vix1d": "vix1d_value",
        "confidence_score": "confidence_score_percent"
    }
    df = df.rename(columns=rename_map)
    
    # Handle NaN values for JSON serialization
    # Convert to object first to allow None replacement
    df = df.astype(object)
    df = df.where(pd.notnull(df), None)
    
    # Convert to list of dicts
    records = df.to_dict(orient="records")
    
    return records

@router.get("/latest")
@router.get("/massive/latest")
async def get_expected_moves_latest():
    """
    Returns the latest Expected Moves analysis (JSON).
    """
    from mie_lib.utils.paths import options_latest_json_path
    import json
    import math

    def sanitize_floats(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: sanitize_floats(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize_floats(x) for x in obj]
        return obj
    
    path = options_latest_json_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Latest Expected Moves data not found")
        
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return sanitize_floats(data)
    except Exception as e:
        logger.error(f"Error reading latest EM data: {e}")
        raise HTTPException(status_code=500, detail="Error reading data")
