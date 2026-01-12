from fastapi import APIRouter, HTTPException, Response
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR, FRED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("coi_index_api")

def get_recession_periods():
    """Load and process USREC data into recession periods."""
    usrec_path = FRED_DATA_DIR / "USREC.parquet"
    if not usrec_path.exists():
        return []
    
    try:
        df = pd.read_parquet(usrec_path)
        # Sort by date column (not index)
        df = df.sort_values('date').reset_index(drop=True)
        df['recession'] = df['value'].fillna(0).astype(int)
        df['recession_start'] = (df['recession'] == 1) & (df['recession'].shift(1) != 1)
        df['recession_end'] = (df['recession'] == 1) & (df['recession'].shift(-1) != 1)
        
        recessions = []
        start_rows = df[df['recession_start']]
        end_rows = df[df['recession_end']]
        
        for i, (_, start_row) in enumerate(start_rows.iterrows()):
            if i < len(end_rows):
                end_row = end_rows.iloc[i]
                recessions.append({
                    "start": pd.to_datetime(start_row['date']).strftime('%Y-%m-%d'),
                    "end": pd.to_datetime(end_row['date']).strftime('%Y-%m-%d')
                })
        return recessions
    except Exception as e:
        LOG.warning(f"Error loading recession data: {e}")
        return []


@router.get("/api/macro/coi-index", response_model=Dict[str, Any])
async def get_coi_index(response: Response):
    """
    Returns the Coincident Indicators Index (COI) data.
    
    Reads from: data/processed/coi_model.parquet
    
    Returns:
        JSON object with 'data' array, 'latest' object, and 'recessions' array.
        - data: Array of {date, coi_composite, signal_line, indpro_yoy, retail_yoy}
        - latest: {score, signal, status, regime, date}
        - recessions: Array of {start, end} date ranges for recession overlays
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    try:
        parquet_file = PROCESSED_DATA_DIR / "coi_model.parquet"
        
        if not parquet_file.exists():
            LOG.warning("COI model data not found.")
            raise HTTPException(
                status_code=503, 
                detail="COI model data not available. Calculation may need to be run."
            )
            
        df = pd.read_parquet(parquet_file)
        
        # Handle NaN/Inf -> None
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        df = df.sort_index()
        
        data = []
        for idx, row in df.iterrows():
            data.append({
                "date": idx.strftime('%Y-%m-%d'),
                "coi_composite": row['coi_composite'],
                "signal_line": row['signal_line'],
                "indpro_yoy": row['indpro_yoy'],
                "retail_yoy": row['retail_yoy']
            })
            
        # Latest reading logic
        latest_reading = {}
        if len(df) > 0:
            latest = df.iloc[-1]
            score = latest['coi_composite']
            signal = latest['signal_line']
            
            # Simple status: Positive = Expansion, Negative = Contraction
            status = "Expansion" if score > 0 else "Contraction"
            regime = "Expansion (Growth)" if score > 0 else "Contraction (Recessionary)"
            
            latest_reading = {
                "score": score,
                "signal": signal,
                "status": status,
                "regime": regime,
                "date": df.index[-1].strftime('%Y-%m-%d')
            }
        
        # Load recession data
        recessions = get_recession_periods()
            
        return {
            "data": data,
            "latest": latest_reading,
            "recessions": recessions
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Error serving COI Index data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

