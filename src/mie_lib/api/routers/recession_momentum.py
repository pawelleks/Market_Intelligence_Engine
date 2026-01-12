from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("recession_momentum_api")

@router.get("/api/macro/nfp-model", response_model=Dict[str, Any])
async def get_nfp_recession_model():
    """
    Returns the Macro-Momentum Recession Model data based on PAYEMS (Nonfarm Payrolls).
    
    Reads from: data/processed/nfp_recession_model.parquet
    
    Returns:
        JSON object with 'data' array and 'metadata' object.
        - data: Array of {date, nfp_mom, nfp_sma_12m, signal, regime}
        - metadata: {current_sma, status, last_updated}
    """
    try:
        parquet_file = PROCESSED_DATA_DIR / "nfp_recession_model.parquet"
        
        if not parquet_file.exists():
            LOG.warning("NFP Recession Model data not found.")
            raise HTTPException(
                status_code=503, 
                detail="NFP Recession Model data not available. Model calculation may need to be run."
            )
            
        df = pd.read_parquet(parquet_file)
        
        # 1. Handle NaN/Inf -> None (JSON Standard)
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        
        # 2. Sort by date ascending
        df = df.sort_index()
        
        # 3. Prepare data array
        data = []
        for idx, row in df.iterrows():
            data.append({
                "date": idx.strftime('%Y-%m-%d'),
                "nfp_mom": row['nfp_mom'],
                "nfp_sma_12m": row['nfp_sma_12m'],
                "recession_signal": row['recession_signal'],
                "regime": row['regime']
            })
        
        # 4. Prepare metadata
        if len(df) > 0:
            latest_row = df.iloc[-1]
            latest_date = df.index[-1].strftime('%Y-%m-%d')
            current_sma = latest_row['nfp_sma_12m']
            status = latest_row['regime']
            
            metadata = {
                "current_sma": f"{current_sma/1000:.2f}k" if current_sma is not None else "N/A",
                "status": status,
                "last_updated": latest_date
            }
        else:
            metadata = {
                "current_sma": "N/A",
                "status": "Unknown",
                "last_updated": None
            }
            
        return {
            "data": data,
            "metadata": metadata
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Error fetching NFP Recession Model data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
