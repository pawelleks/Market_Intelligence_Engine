from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

from mie_lib.analytics.gex.gex_engine import GEXEngine
import pandas as pd
from pathlib import Path
import glob
import os

# Setup Router
router = APIRouter(prefix="/api/v1/gex", tags=["Gamma Exposure"])
logger = logging.getLogger(__name__)

# In-Memory Cache
# Structure: {ticker: {"timestamp": datetime, "data": dict}}
_GEX_CACHE: Dict[str, Dict] = {}
CACHE_TTL_MINUTES = 15

def sanitize_floats(obj):
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_floats(x) for x in obj]
    return obj

@router.get("/latest/{ticker}")
def get_latest_gex(ticker: str, force_refresh: bool = False):
    """
    Returns the latest Gamma Exposure (GEX) profile for a ticker.
    STRICTLY prefers persistent storage (Daily Build).
    Only calculates on-demand if:
    1. Data is completely missing from disk.
    2. force_refresh=True is passed.
    """
    ticker = ticker.upper().strip()
    
    from mie_lib.analytics.gex.storage import load_gex_profile
    
    # 1. Try In-Memory Cache (Fastest)
    if not force_refresh and ticker in _GEX_CACHE:
        # Simple TTL check for memory cache
        entry = _GEX_CACHE[ticker]
        age = datetime.now() - entry["timestamp"]
        if age < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info(f"Serving GEX for {ticker} from memory cache")
            return entry["data"]
            
    # 2. Try Disk Storage (Daily Build)
    if not force_refresh:
        disk_data = load_gex_profile(ticker)
        if disk_data:
            # Check if profile is valid
            if disk_data.get("profile"):
                logger.info(f"Serving GEX for {ticker} from disk (Daily Build)")
                # Update memory cache
                sanitized_data = sanitize_floats(disk_data)
                _GEX_CACHE[ticker] = {"timestamp": datetime.now(), "data": sanitized_data}
                return sanitized_data
            else:
                 logger.warning(f"GEX disk data for {ticker} exists but empty profile.")

    # 3. Fallback: Calculate On-Demand (Only if missing or forced)
    logger.info(f"Calculating GEX for {ticker} (On-Demand: Missing Data or Forced)...")
    try:
        engine = GEXEngine()
        data = engine.fetch_and_calculate_gex(ticker)
        
        if not data:
             # Last ditch: try loading old disk data even if we just failed calc?
             # Or just 404
             raise HTTPException(status_code=404, detail=f"Could not calculate GEX for {ticker} and no history found.")
            
        # Update Cache
        sanitized_data = sanitize_floats(data)
        _GEX_CACHE[ticker] = {
            "timestamp": datetime.now(),
            "data": sanitized_data
        }
        
        return sanitized_data
    except Exception as e:
         logger.error(f"GEX Error: {e}")
         raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit/{ticker}")
def get_gex_audit(ticker: str):
    """
    Mode: BATCH (read-only)
    Data Source: Pre-computed audit report from disk
    Response Time: <50ms

    Returns the latest GEX audit report comparing ThetaData vs yfinance calculations.
    """
    import json

    ticker = ticker.upper().strip()
    audit_path = Path("data/analytics/gex") / f"audit_{ticker}.json"

    if not audit_path.exists():
        raise HTTPException(status_code=404, detail=f"No audit report found for {ticker}. Run 'audit-gex' first.")

    with open(audit_path) as f:
        return json.load(f)


@router.get("/history/heatmap/{ticker}")
def get_gex_history_heatmap(ticker: str):
    """
    Returns aggregated historical GEX data for heatmap visualization.
    Structure:
    {
        "x": [dates...],
        "y": [strikes...],
        "z": [[gex_t0_s0, gex_t0_s1...], ...],
        "available_dates": [dates...]
    }
    """
    ticker = ticker.upper().strip()
    history_dir = Path("data/analytics/gex/history")
    
    # 1. Glob files
    # Expected: SPY_profile_YYYYMMDD.parquet
    pattern = str(history_dir / f"{ticker}_profile_*.parquet")
    files = glob.glob(pattern)
    
    if not files:
        # Fallback to just SPY_profile_YYYYMMDD if ticker matches (sometimes case issues)
        if ticker == "SPY": 
             pattern = str(history_dir / "SPY_profile_*.parquet")
             files = glob.glob(pattern)
    
    files = sorted(files)
    
    if not files:
         raise HTTPException(status_code=404, detail=f"No historical GEX data found for {ticker}")

    # 2. Iterate and Load
    all_profiles = []
    
    for f in files:
        try:
            # Extract date from filename: ..._YYYYMMDD.parquet
            basename = os.path.basename(f)
            # regex or simple split
            # SPY_profile_20251216.parquet
            parts = basename.split('_')
            date_part = parts[-1].replace('.parquet', '')
            
            # Convert YYYYMMDD to YYYY-MM-DD
            dt_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}"
            
            df = pd.read_parquet(f)
            # df columns: strike, total_net_gex, ...
            # We want strike and total_net_gex
            if 'strike' not in df.columns or 'total_net_gex' not in df.columns:
                continue
                
            # Filter essential columns to save memory
            subset = df[['strike', 'total_net_gex']].copy()
            subset['date'] = dt_str
            all_profiles.append(subset)
            
        except Exception as e:
            logger.warning(f"Error reading {f}: {e}")
            continue
            
    if not all_profiles:
         raise HTTPException(status_code=404, detail="Could not load any valid historical profiles.")

    # 3. Pivot
    full_df = pd.concat(all_profiles)
    
    # Pivot: Index=Strike, Columns=Date, Values=GEX
    pivot_df = full_df.pivot(index='strike', columns='date', values='total_net_gex')
    
    # Fill NaN with 0 (no GEX at that strike)
    pivot_df = pivot_df.fillna(0.0)
    
    # Sort Index (Strikes) and Columns (Dates)
    pivot_df = pivot_df.sort_index().sort_index(axis=1)
    
    # Extract components
    strikes = pivot_df.index.tolist()
    dates = pivot_df.columns.tolist()
    
    # Z matrix: Transpose so X=Date is rows? No, Plotly Heatmap usually:
    # z: [[z11, z12, ...], [z21, z22, ...]]
    # usually z[y][x]. y is rows (strikes), x is cols (dates).
    # So we want values as list of lists, row by row (strike by strike).
    z_values = pivot_df.values.tolist()
    
    # 4. Construct Response
    return {
        "x": dates,
        "y": strikes,
        "z": z_values, # Array of arrays: Outer index corresponds to Y (Strikes), Inner to X (Dates)
        "available_dates": dates
    }
