
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("hamilton_filter_api")

@router.get("/api/v1/analysis/hamilton-filter", response_model=Dict[str, Any])
async def get_hamilton_filter_data():
    """
    Returns the Hamilton Markov Switching Model recession probabilities.
    
    Reads from: data/processed/hamilton_model.parquet
    
    Returns:
        JSON object with 'data' array and 'latest_reading' object.
        - data: Array of {date, recession_prob, growth_rate}
        - latest_reading: {probability, regime}
    """
    try:
        parquet_file = PROCESSED_DATA_DIR / "hamilton_model.parquet"
        
        if not parquet_file.exists():
            LOG.warning("Hamilton model data not found.")
            raise HTTPException(status_code=503, detail="Hamilton Model data not available. Model may need to be run.")
            
        df = pd.read_parquet(parquet_file)
        
        # 1. Handle NaN/Inf -> None (JSON Standard)
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        
        # 2. Sort by date ascending (oldest to newest) for frontend charting
        df = df.sort_index()
        
        # 3. Prepare data array
        # Ensure 'date' is string YYYY-MM-DD with quarter notation
        data = []
        for idx, row in df.iterrows():
            quarter = (idx.month - 1) // 3 + 1
            data.append({
                "date": f"{idx.year}-Q{quarter}",
                "recession_prob": row['recession_prob'],
                "growth_rate": row['growth_rate']
            })
        
        # 4. Calculate latest reading
        if len(df) > 0:
            latest_row = df.iloc[-1]
            latest_prob = latest_row['recession_prob']
            
            # Regime classification: > 50% = Recession, else Expansion
            regime = "Recession" if latest_prob > 0.5 else "Expansion"
            
            latest_reading = {
                "probability": latest_prob,
                "regime": regime
            }
        else:
            latest_reading = {
                "probability": None,
                "regime": "Unknown"
            }
            
        return {
            "data": data,
            "latest_reading": latest_reading
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Error fetching Hamilton Filter data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
