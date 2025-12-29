from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Optional, Any
import logging
from pathlib import Path
import json
from datetime import date

from mie_lib.analytics.skew import storage
from mie_lib.analytics.skew.skew_pipeline import _fetch_yfinance_chain_hybrid

router = APIRouter(
    prefix="/api/v1/analytics/skew",
    tags=["Analytics - Skew & PCR"]
)

logger = logging.getLogger(__name__)

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

def _format_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to convert flat storage format back to nested frontend format."""
    return {
        "date": str(row.get("date")),
        "ticker": row.get("ticker"),
        "underlying_price": row.get("spot"),
        "pcr_metrics": {
            "total_volume_pcr": row.get("pcr_volume"),
            "total_oi_pcr": row.get("pcr_oi")
        },
        "skew_metrics": {
            "skew_25d_1m": row.get("skew_25d")
        },
        "regime": row.get("regime"),
        "sentiment_score": row.get("sentiment_score"),
        "source": row.get("source"),
        "meta": {
            "computed_at": str(row.get("computed_at", ""))
        }
    }

@router.get("/{ticker}/latest")
def get_latest_skew(ticker: str):
    """
    Get the most recent Skew and PCR record for a ticker.
    """
    try:
        latest_data = storage.load_latest()
        ticker_upper = ticker.upper()
        
        if ticker_upper in latest_data.get("tickers", {}):
            ticker_metrics = latest_data["tickers"][ticker_upper]
            # Construct a record compatible with frontend
            return sanitize_floats({
                "date": latest_data.get("as_of"),
                "ticker": ticker_upper,
                "underlying_price": ticker_metrics.get("spot"),
                "pcr_metrics": {
                    "total_volume_pcr": ticker_metrics.get("pcr_volume"),
                    "total_oi_pcr": ticker_metrics.get("pcr_oi")
                },
                "skew_metrics": {
                    "skew_25d_1m": ticker_metrics.get("skew_25d")
                },
                "regime": ticker_metrics.get("regime"),
                "sentiment_score": ticker_metrics.get("sentiment_score")
            })
            
        return {}
        
    except Exception as e:
        logger.error(f"Error fetching latest skew for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{ticker}/history")
def get_skew_history(ticker: str):
    # ... existing implementation ...
    try:
        df = storage.load_ticker_history(ticker.upper(), days=120)
        if df is None or df.empty:
            return []
            
        # Convert DataFrame to list of formatted dicts
        records = df.to_dict('records')
        return sanitize_floats([_format_record(r) for r in records])
        
    except Exception as e:
        logger.error(f"Error fetching skew history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{ticker}/curve")
def get_skew_curve(ticker: str):
    """
    Get raw strike/IV data for multiple expirations to plot the volatility smile.
    """
    try:
        # 1. Fetch Latest Data to get current Spot Price
        latest_all = storage.load_latest()
        latest_ticker = latest_all.get("tickers", {}).get(ticker.upper(), {})
        spot = latest_ticker.get("spot")
        
        # 2. Fetch Option Chains (limit to 110 days to include March monthly)
        df = _fetch_yfinance_chain_hybrid(ticker.upper(), target_dte_min=7, target_dte_max=110)
        
        if df.empty:
            return {"ticker": ticker, "expirations": {}, "spot": spot}
            
        # 3. Apply Filters for Readability
        if spot:
            # Filter for Strikes within +/- 15% of spot
            margin = 0.15
            df = df[(df["strike"] >= spot * (1 - margin)) & (df["strike"] <= spot * (1 + margin))]
            
            # SKEW FIX: Only use OTM options to avoid "zig-zags" (multiple IVs per strike)
            # Puts for Strike < Spot, Calls for Strike >= Spot
            is_put_otm = (df["type"].str.lower() == "put") & (df["strike"] < spot)
            is_call_otm = (df["type"].str.lower() == "call") & (df["strike"] >= spot)
            df = df[is_put_otm | is_call_otm]
            
        # Filter out extreme IV noise (> 150%)
        df = df[df["iv"] < 1.5]
        
        # Group by expiration
        expirations = {}
        for exp, group in df.groupby("expiration"):
            # Sort by strike for smooth lines
            group = group.sort_values("strike")
            
            # Filter out 0 IVs
            group = group[group["iv"] > 0]
            
            if not group.empty:
                expirations[str(exp)] = group[["strike", "iv", "type"]].to_dict("records")
            
        return sanitize_floats({
            "ticker": ticker.upper(),
            "as_of": str(date.today()),
            "spot": spot,
            "expirations": expirations
        })
        
    except Exception as e:
        logger.error(f"Error fetching skew curve for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{ticker}/refresh")
def refresh_skew(ticker: str, background_tasks: BackgroundTasks):
    """
    Trigger a backfill/refresh of Skew data using the parallel pipeline.
    """
    from mie_lib.analytics.skew.skew_pipeline import run_skew_pipeline_parallel
    
    ticker_upper = ticker.upper()
    # We run for today + last trading day to be sure
    background_tasks.add_task(run_skew_pipeline_parallel, [ticker_upper])
    
    return {"status": "Refresh triggered", "ticker": ticker_upper}
