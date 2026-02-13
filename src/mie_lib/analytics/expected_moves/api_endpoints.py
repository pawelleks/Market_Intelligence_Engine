from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import pandas as pd
from pathlib import Path
import logging

from mie_lib.analytics.expected_moves.models import HistoricalEMRecord
from mie_lib.analytics.expected_moves.theta_expected_moves_engine import ThetaExpectedMovesEngine

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

    Mode: BATCH
    Data Source: All *_expected_moves.parquet files in data/analytics/options/
    Response Time: <200ms

    Returns a list of dicts with:
    - ticker: str (e.g. "SPY")
    - expiry_type: str (e.g. "WEEKLY", "ODTE")
    - total_records: int (number of finalized records)
    - hit_rate_percent: float (% of times close stayed within EM range)
    - average_high_breach_dollars: float (average breach amount in dollars)
    - max_breach_percent: float (largest % overshoot/undershoot)

    Only includes finalized records where closed_within_em is not null.
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

    Mode: BATCH
    Data Source: *_expected_moves.parquet files (filtered by query params)
    Response Time: <100ms

    Query Parameters:
    - ticker: Optional[str] - Filter by ticker (e.g. "SPY"). Case-insensitive.
    - expiry_type: Optional[str] - Filter by expiry type (e.g. "WEEKLY", "ODTE").

    Returns List[HistoricalEMRecord] with fields: ticker, expiry_type, expiry_date,
    underlying_price, expected_move_dollars, upper_range, lower_range, vix1d_value,
    confidence_score_percent, timestamp, and realized metrics when available.
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
    Returns the latest Expected Moves analysis from the batch pipeline.

    Mode: BATCH (pure file serving, no computation)
    Data Source: data/analytics/options/latest.json
    Response Time: <50ms

    The JSON is generated by the daily pipeline (update-expected-moves) and
    uses a date-precedence merge strategy to prevent overwriting newer data
    with older calculations. NaN/Inf values are sanitized to null.

    Both /latest and /massive/latest serve the same data.
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

@router.get("/static/latest")
async def get_static_expected_moves():
    """
    Serves pre-computed static Expected Moves from a JSON file.

    Mode: BATCH (instant file serving, no live computation)
    Data Source: /app/public/data/expected_moves_static.json
    Response Time: <10ms
    Generated by: jobs/process_expected_moves_static.py (cron or on startup)

    Differs from /latest: this endpoint serves data computed by the Theta-based
    static pipeline (using ThetaData REST API for spot + options), while /latest
    serves data from the Massive/Polygon batch pipeline.

    Calculation: EM = Straddle_Price * 0.85 (sigma factor)
    """
    import json
    static_path = Path("/app/public/data/expected_moves_static.json")
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Static EM data not available. Waiting for first computation.")
    try:
        with open(static_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading static EM data: {e}")
        raise HTTPException(status_code=500, detail="Error reading static EM data")

@router.get("/theta/latest/{ticker}")
async def get_theta_expected_moves(ticker: str):
    """
    Returns Expected Moves calculated live from ThetaData REST API.

    Mode: REAL-TIME (live calculation on every request)
    Data Source: Theta Terminal REST API (port 25510)
    Response Time: 2-5 seconds (Theta API latency)
    Independent of: Massive CSV / Polygon / yfinance pipelines

    Path Parameters:
    - ticker: str - Ticker symbol (e.g. "SPY", "SPX", "QQQ", "IWM")

    Calculation Flow:
    1. Fetch spot price via /v2/hist/stock/eod or /v2/hist/index/eod
    2. Determine expirations (0DTE, WEEKLY, MONTHLY)
    3. Fetch ATM straddle via /v2/bulk_snapshot/option/quote
    4. Apply bad tick filter + estimation for missing data
    5. EM = straddle_price * 0.85 (sigma factor)

    Returns JSON with high/low/plus_minus per expiration type, plus debug info.

    Requires: Theta Terminal running (THETA_HOST, THETA_REST_PORT env vars).
    """
    import os
    host = os.getenv("THETA_HOST", "theta_terminal")
    port = int(os.getenv("THETA_REST_PORT", "25510"))
    engine = ThetaExpectedMovesEngine(host=host, port=port)
    try:
        result = engine.run(ticker.upper())
        return result
    finally:
        engine.close()

