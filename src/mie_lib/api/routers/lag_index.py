from fastapi import APIRouter, HTTPException, Response
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR, FRED_DATA_DIR

router = APIRouter()
LOG = logging.getLogger("lag_index_api")

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


@router.get("/api/macro/lag-index", response_model=Dict[str, Any])
async def get_lag_index(response: Response):
    """
    Returns the Lagging Indicators Index (LAG) data plus the LEI divergence.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    try:
        parquet_file = PROCESSED_DATA_DIR / "lag_model.parquet"
        divergence_file = PROCESSED_DATA_DIR / "fed_trap_divergence.parquet"
        
        if not parquet_file.exists():
            LOG.warning("LAG model data not found.")
            raise HTTPException(
                status_code=503, 
                detail="LAG model data not available."
            )
            
        df = pd.read_parquet(parquet_file)
        
        # Merge Risk Spread if available
        if divergence_file.exists():
            div_df = pd.read_parquet(divergence_file)
            df = df.join(div_df[['risk_spread', 'lei']], how='left')
        else:
            df['risk_spread'] = None
            df['lei'] = None
        
        # Handle NaN/Inf -> None
        df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
        df = df.sort_index()
        
        data = []
        for idx, row in df.iterrows():
            data.append({
                "date": idx.strftime('%Y-%m-%d'),
                "lag_composite": row['lag_composite'],
                "signal_line": row['signal_line'],
                "lei": row['lei'],
                "risk_spread": row['risk_spread'],
                "cpi_serv": row['cpi_serv_yoy'],
                "unrate": row['unrate_inverted'],
                "ulc": row['ulc_yoy'],
                "loans": row['loans_yoy']
            })
            
        # Latest reading logic
        latest_reading = {}
        if len(df) > 0:
            latest = df.iloc[-1]
            score = latest['lag_composite']
            signal = latest['signal_line']
            
            # LAG status: Higher = Overheating/Confirmation of cycle top
            status = "Overheating" if score > 0 else "Cooling"
            
            latest_reading = {
                "lag_composite": score,
                "signal_line": signal,
                "score": score,  # Keep for backwards compatibility
                "signal": signal,  # Keep for backwards compatibility
                "lei": latest.get('lei'),
                "risk_spread": latest.get('risk_spread'),
                "status": status,
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
        LOG.error(f"Error serving LAG Index data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

