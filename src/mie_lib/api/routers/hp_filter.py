
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("hp_filter_api")

@router.get("/api/v1/analysis/hp-filter", response_model=Dict[str, Any])
async def get_hp_filter_data():
    """
    Returns the Hodrick-Prescott (HP) Filter Model Indicators for Output Gap and Credit Gap.
    
    Reads from: data/processed/hp_model.parquet
    
    Returns:
        JSON object with 'dates' and 'indicators'.
        Standardized Columns:
        - real_gdp: The Actual GDP
        - gdp_trend: The Potential GDP
        - output_gap: The GDP Cycle %
        - credit_gap: The Credit Cycle %
    """
    try:
        parquet_file = PROCESSED_DATA_DIR / "hp_model.parquet"
        
        if not parquet_file.exists():
            LOG.warning("HP Filter model data not found.")
            raise HTTPException(status_code=404, detail="HP Model data not found.")
            
        df = pd.read_parquet(parquet_file)
        
        # 1. Handle NaN/Inf -> None (JSON Standard)
        # Note: statsmodels might produce some NaNs at the very edges of the series
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        
        # 2. Prepare Response Structure
        # Ensure 'date' is string YYYY-MM-DD
        dates = df.index.strftime('%Y-%m-%d').tolist()
        
        # We only return the specific columns requested by the user for Phase 2:
        # real_gdp, gdp_trend, output_gap, credit_gap
        # Note: real_credit and credit_trend are currently not explicitly requested in Phase 2 response but exist in file.
        
        target_columns = ['real_gdp', 'gdp_trend', 'output_gap', 'credit_gap']
        indicators = {}
        for col in target_columns:
            if col in df.columns:
                indicators[col] = df[col].tolist()
            else:
                indicators[col] = [None] * len(dates)
                LOG.warning(f"Column {col} missing from hp_model.parquet")
            
        return {
            "dates": dates,
            "indicators": indicators
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Error fetching HP Filter data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
