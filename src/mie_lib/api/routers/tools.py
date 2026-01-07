from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from mie_lib.analytics.tools.ema_respect import analyze_ticker

router = APIRouter()

@router.get("/tools/ema-respect")
async def get_ema_respect(
    ticker: str,
    tolerance: float = 0.5,
    proximity: float = 1.0,
    min_period: int = 10,
    max_period: int = 300,
    short_min: int = 10,
    short_max: int = 60,
    medium_min: int = 61,
    medium_max: int = 140,
    long_min: int = 141,
    long_max: int = 300,
    ma_type: str = "EMA"
) -> Dict[str, Any]:
    """
    Analyze EMA respect scores for a ticker.
    """
    if tolerance < 0 or proximity < 0:
        raise HTTPException(status_code=400, detail="Parameters must be positive")
        
    ranges = {
        'short': {'min': short_min, 'max': short_max},
        'medium': {'min': medium_min, 'max': medium_max},
        'long': {'min': long_min, 'max': long_max}
    }
        
    result = analyze_ticker(
        ticker.upper(), 
        tolerance=tolerance, 
        proximity=proximity,
        min_period=min_period,
        max_period=max_period,
        ranges=ranges,
        ma_type=ma_type
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return {
        "status": "ok",
        "data": result
    }
