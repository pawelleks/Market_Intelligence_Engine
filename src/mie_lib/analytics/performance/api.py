"""
API Endpoint for Market Performance.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel
from datetime import date

from mie_lib.utils.config import load_named_config
from mie_lib.analytics.performance.engine import calculate_performance_snapshot, calculate_sector_history, calculate_sector_correlations

router = APIRouter()
LOG = logging.getLogger(__name__)

class PerformanceRow(BaseModel):
    ticker: str
    group: str
    sector: Optional[str] = None
    price: float
    asof_date: date
    ret_1d: Optional[float]
    ret_1w: Optional[float]
    ret_1m: Optional[float]
    ret_3m: Optional[float]
    ret_6m: Optional[float]
    ret_1y: Optional[float]
    ret_ytd: Optional[float]
    high_52w: Optional[float]
    low_52w: Optional[float]
    pct_52w: Optional[float]

@router.get("/snapshot", response_model=List[PerformanceRow])
def get_performance_snapshot():
    """
    Returns performance metrics for all configured tickers,
    enriched with Group information from config.
    """
    # 1. Load Config
    try:
        # Load 'ticker_groups' content
        group_config = load_named_config("ticker_groups")
        
        # Also need 'ticker_list' to get Sectors if available, or just rely on manual mapping?
        # For now, we will derive 'Group' from ticker_groups.yml.
        # Sector might be available in 'ticker_list.yml' detailed view.
        ticker_list_cfg = load_named_config("ticker_list")
        
        # Build Ticker -> Group Map
        ticker_to_group = {}
        for grp_name, ticker_list in group_config.get("groups", {}).items():
            for t in ticker_list:
                ticker_to_group[str(t).upper()] = grp_name.replace("_", " ") # Format "Index ETFs"

        # Build Ticker -> Sector Map (optional)
        ticker_to_sector = {}
        if "tickers" in ticker_list_cfg and isinstance(ticker_list_cfg["tickers"], dict):
             for t, meta in ticker_list_cfg["tickers"].items():
                 if isinstance(meta, dict) and "sector" in meta:
                     ticker_to_sector[str(t).upper()] = meta["sector"]

    except Exception as e:
        LOG.error(f"Failed to load configs: {e}")
        raise HTTPException(status_code=500, detail="Configuration Error")

    # 2. Identify All Tickers to Process
    # We want to show everything in the groups config
    target_tickers = list(ticker_to_group.keys())

    # 3. Calculate Performance
    # This might take a few seconds - caching strategy recommended for prod, but direct for now
    raw_data = calculate_performance_snapshot(target_tickers)

    # 4. Enrich & Format
    response = []
    for row in raw_data:
        t = row["ticker"].upper()
        row["group"] = ticker_to_group.get(t, "Uncategorized")
        row["sector"] = ticker_to_sector.get(t, None)
        response.append(row)
        
    return response

@router.get("/history", response_model=Dict[str, Any])
def get_performance_history():
    """
    Returns historical cumulative performance (1Y and 12M Rolling) for Sector ETFs + SPY.
    """
    try:
        # Load Config to get Sector ETFs
        group_config = load_named_config("ticker_groups")
        target_tickers = []
        if "groups" in group_config and "Sector_ETFs" in group_config["groups"]:
            target_tickers = group_config["groups"]["Sector_ETFs"]
            
        # Ensure SPY is included for reference
        if "SPY" not in target_tickers:
            target_tickers.append("SPY")
            
        # Defensive copy/cast
        target_tickers = [str(t).upper() for t in target_tickers]
        
        return calculate_sector_history(target_tickers)
        
    except Exception as e:
        LOG.error(f"Failed to calculate history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
@router.get("/correlation", response_model=Dict[str, Any])
def get_sector_correlations():
    """
    Returns 2 correlation matrices (Calendar Year, Rolling 12M).
    """
    try:
        group_config = load_named_config("ticker_groups")
        target_tickers = []
        if "groups" in group_config and "Sector_ETFs" in group_config["groups"]:
            target_tickers = group_config["groups"]["Sector_ETFs"]
            
        target_tickers = [str(t).upper() for t in target_tickers]
        return calculate_sector_correlations(target_tickers)
        
    except Exception as e:
        LOG.error(f"Failed to calculate correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
