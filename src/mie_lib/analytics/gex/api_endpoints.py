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
            from mie_lib.utils.trading_calendar import get_previous_trading_day, coerce_to_date
            
            # Check timestamp age AND target date freshness
            try:
                # 2.1 Check JSON timestamp (TTL)
                ts = datetime.fromisoformat(disk_data.get("timestamp"))
                is_recent = (datetime.now() - ts).total_seconds() < (max_age_hours * 3600)
                
                # 2.2 Check Data Target Date (Business Logic Freshness)
                # If today is Tuesday, and data is from Friday, it's stale (Monday is missing).
                target_date_str = disk_data.get("date") # We added 'date' to results in engine
                if not target_date_str:
                    # Fallback for legacy data without 'date' key
                    # Force refresh if older than 12 hours
                    is_recent = (datetime.now() - ts).total_seconds() < (12 * 3600)
                else:
                    target_date = coerce_to_date(target_date_str)
                    prev_trading_day = get_previous_trading_day(date.today())
                    
                    if target_date < prev_trading_day:
                        logger.warning(f"GEX disk data for {ticker} is stale (Data: {target_date}, Required: {prev_trading_day}). Forcing refresh.")
                        is_recent = False
                
                if is_recent:
                     # Validate Profile Data exists
                     if not disk_data.get("profile"):
                         logger.warning(f"GEX disk data for {ticker} missing profile. Ignoring.")
                     else:
                         logger.info(f"Serving GEX for {ticker} from disk")
                         # Update memory cache
                         sanitized_data = sanitize_floats(disk_data)
                         _GEX_CACHE[ticker] = {"timestamp": datetime.now(), "data": sanitized_data}
                         return sanitized_data
            except Exception as e:
                logger.warning(f"Error validating GEX disk data for {ticker}: {e}")
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
        sanitized_data = sanitize_floats(data)
        _GEX_CACHE[ticker] = {
            "timestamp": datetime.now(),
            "data": sanitized_data
        }
        
        return sanitized_data
    except Exception as e:
         logger.error(f"GEX Error: {e}")
         raise HTTPException(status_code=500, detail=str(e))
