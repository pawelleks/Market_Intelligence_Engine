from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

from mie_lib.analytics.gex.gex_engine import GEXEngine

# Setup Router
router = APIRouter(prefix="/api/v1/gex", tags=["Gamma Exposure"])
logger = logging.getLogger(__name__)

# In-Memory Cache
# Structure: {ticker: {"timestamp": datetime, "data": dict}}
_GEX_CACHE: Dict[str, Dict] = {}
CACHE_TTL_MINUTES = 15

@router.get("/latest/{ticker}")
def get_latest_gex(ticker: str, force_refresh: bool = False):
    """
    Returns the latest Gamma Exposure (GEX) profile for a ticker.
    Checks persistent storage first, then (optionally) falls back to on-demand calc.
    """
    ticker = ticker.upper().strip()
    
    from mie_lib.analytics.gex.storage import load_gex_profile
    
    if not force_refresh:
        # 1. Try In-Memory Cache first
        if ticker in _GEX_CACHE:
            entry = _GEX_CACHE[ticker]
            age = datetime.now() - entry["timestamp"]
            if age < timedelta(minutes=CACHE_TTL_MINUTES):
                logger.info(f"Serving GEX for {ticker} from memory cache")
                return entry["data"]
                
        # 2. Try Persistent Storage (Disk)
        max_age_hours = 24 # Daily builds
        disk_data = load_gex_profile(ticker)
        if disk_data:
            # Check timestamp age
            try:
                ts = datetime.fromisoformat(disk_data.get("timestamp"))
                if (datetime.now() - ts).total_seconds() < (max_age_hours * 3600):
                     logger.info(f"Serving GEX for {ticker} from disk")
                     # Update memory cache
                     _GEX_CACHE[ticker] = {"timestamp": datetime.now(), "data": disk_data}
                     return disk_data
            except:
                pass
            
    # Calculate (Fallback to yfinance on demand if configured, but plan says we want to move away)
    # For now, we keep the fallback but log it.
    logger.info(f"Calculating GEX for {ticker} (On-Demand)...")
    try:
        engine = GEXEngine()
        data = engine.fetch_and_calculate_gex(ticker)
        
        if not data:
             # Try returning stale disk data if new calc fails
             disk_data = load_gex_profile(ticker)
             if disk_data:
                 return disk_data
                 
             if ticker in _GEX_CACHE:
                 return _GEX_CACHE[ticker]["data"]
                 
             raise HTTPException(status_code=404, detail=f"Could not calculate GEX for {ticker}.")
            
        # Update Cache
        _GEX_CACHE[ticker] = {
            "timestamp": datetime.now(),
            "data": data
        }
        
        return data
    except Exception as e:
         logger.error(f"GEX Error: {e}")
         raise HTTPException(status_code=500, detail=str(e))
