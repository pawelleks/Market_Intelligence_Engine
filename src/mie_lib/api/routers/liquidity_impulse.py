
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("liquidity_impulse_api")

@router.get("/api/v1/analysis/liquidity-impulse", response_model=Dict[str, Any])
async def get_liquidity_impulse_data():
    """
    Returns the Global Liquidity Impulse data aggregating Fed, ECB, and BoJ balance sheets.
    
    Reads from: data/processed/liquidity_impulse.parquet
    
    Returns:
        JSON object with 'data' array and 'latest_reading' object.
        - data: Array of {date, global_liquidity_usd, liquidity_impulse, components{fed, ecb, boj}}
        - latest_reading: {total_liquidity, impulse, trend}
    """
    try:
        parquet_file = PROCESSED_DATA_DIR / "liquidity_impulse.parquet"
        
        if not parquet_file.exists():
            LOG.warning("Liquidity Impulse data not found.")
            raise HTTPException(
                status_code=503, 
                detail="Global Liquidity data not available. Model may need to be run."
            )
            
        df = pd.read_parquet(parquet_file)
        
        # 1. Handle NaN/Inf -> None (JSON Standard)
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        
        # 2. Sort by date ascending (oldest to newest) for frontend charting
        df = df.sort_index()
        
        # 3. Prepare data array
        data = []
        for idx, row in df.iterrows():
            data.append({
                "date": idx.strftime('%Y-%m-%d'),
                "global_liquidity_usd": row['global_liquidity_smooth'],  # Use smoothed version
                "liquidity_impulse": row['liquidity_impulse'],
                "components": {
                    "fed": row['fed_assets_usd'],
                    "ecb": row['ecb_assets_usd'],
                    "boj": row['boj_assets_usd']
                }
            })
        
        # 4. Calculate latest reading
        if len(df) > 0:
            latest_row = df.iloc[-1]
            latest_liquidity = latest_row['global_liquidity_smooth']
            latest_impulse = latest_row['liquidity_impulse']
            
            # Trend classification: > 0 = Expanding, else Contracting
            trend = "Expanding" if latest_impulse > 0 else "Contracting"
            
            latest_reading = {
                "total_liquidity": latest_liquidity,
                "impulse": latest_impulse,
                "trend": trend
            }
        else:
            latest_reading = {
                "total_liquidity": None,
                "impulse": None,
                "trend": "Unknown"
            }
            
        return {
            "data": data,
            "latest_reading": latest_reading
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Error fetching Global Liquidity data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
