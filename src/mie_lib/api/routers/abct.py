
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("abct_api")

@router.get("/api/abct-data", response_model=Dict[str, Any])
@router.get("/api/v1/analysis/abct", response_model=Dict[str, Any])
async def get_abct_data():
    """
    Returns the Austrian Business Cycle Theory (ABCT) Model Indicators.
    
    Reads from: data/processed/abct_model.parquet
    
    Returns:
        JSON object with 'dates' and 'indicators'.
        Standardized Columns:
        - money_supply_growth (M2 YoY)
        - savings_rate (Personal Savings Rate)
        - malinvestment_ratio (PPI Capital / CPI)
        - boom_score (Composite ABCT Score)
        - recession_flag (USREC)
    """
    try:
        parquet_file = PROCESSED_DATA_DIR / "abct_model.parquet"
        
        if not parquet_file.exists():
            LOG.warning("ABCT model data not found.")
            raise HTTPException(status_code=404, detail="Model data not generated.")
            
        df = pd.read_parquet(parquet_file)
        
        # 1. Create Aliases for User Requested API Standards
        # Ensure we have the latest column names from the calculation script
        # Calculate M2 YoY if missing (it might be named 'm2_yoy' in file)
        
        if 'm2_yoy' in df.columns:
            df['money_supply_growth'] = df['m2_yoy']
            
        if 'PSAVERT' in df.columns:
            df['savings_rate'] = df['PSAVERT']
            
        if 'abct_boom_score' in df.columns:
            df['boom_score'] = df['abct_boom_score']
            
        if 'USREC' in df.columns:
            df['recession_flag'] = df['USREC']
            
        # malinvestment_ratio is already named correctly
        
        # 2. Handle NaN/Inf -> None
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        
        # 3. Prepare Response
        dates = df.index.strftime('%Y-%m-%d').tolist()
        
        indicators = {}
        for col in df.columns:
            indicators[col] = df[col].tolist()
            
        return {
            "dates": dates,
            "indicators": indicators
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Error fetching ABCT data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
