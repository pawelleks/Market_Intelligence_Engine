from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from mie_lib.utils.paths import PROCESSED_DATA_DIR

router = APIRouter()

MINSKY_PARQUET_PATH = PROCESSED_DATA_DIR / "minsky_model.parquet"

@router.get("/api/minsky-data")
def get_minsky_data():
    """Retrieves the pre-calculated Minsky Financial Instability indicators."""
    if not MINSKY_PARQUET_PATH.exists():
        raise HTTPException(status_code=404, detail="Minsky model data not found. Run calculation script first.")
    
    try:
        df = pd.read_parquet(MINSKY_PARQUET_PATH)
        
        # Ensure date index is a column and formatted
        df = df.reset_index()
        # The index name might be 'date' or None. If it's the index, reset_index makes it a col.
        # But wait, script line 50: minsky_df = pd.concat(dfs, axis=1).sort_index()
        # The index is 'date' (datetime).
        
        # Check if 'date' is effectively the column name now
        if 'date' not in df.columns and 'index' in df.columns:
            df.rename(columns={'index': 'date'}, inplace=True)
            
        # Format date as ISO string
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Replace NaNs for JSON
        df = df.replace({np.nan: None})
        
        # Structure for charting optimization if desired, but "list of records" is versatile
        # User prompt suggested: { "dates": [...], "indicators": { "debt_service": [...], ... } }
        # Let's do that for efficiency if requested, or at least offer it. 
        # User said: "Structure it as a list of records, or better yet, a structure optimized for charting"
        # I will implement the "optimized" structure.
        
        data = {
            "dates": df['date'].tolist(),
            "indicators": {
                col: df[col].tolist() for col in df.columns if col != 'date'
            }
        }
        
        return JSONResponse(content=data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading Minsky data: {e}")

@router.get("/api/status")
def get_minsky_status():
    """Returns the timestamp of the last data update."""
    if not MINSKY_PARQUET_PATH.exists():
         return JSONResponse(content={"status": "not_found", "last_updated": None})
    
    try:
        # Get file modification time
        mtime = MINSKY_PARQUET_PATH.stat().st_mtime
        last_updated = datetime.fromtimestamp(mtime).isoformat()
        
        return JSONResponse(content={
            "status": "ready",
            "last_updated": last_updated,
            "path": str(MINSKY_PARQUET_PATH)
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

MINSKY_VALIDATION_PATH = PROCESSED_DATA_DIR / "minsky_market_validation.parquet"

@router.get("/api/minsky-market-data")
def get_minsky_market_data():
    """Retrieves the merged Minsky + Market data for validation charts."""
    if not MINSKY_VALIDATION_PATH.exists():
        raise HTTPException(status_code=404, detail="Minsky validation data not found.")
    
    try:
        df = pd.read_parquet(MINSKY_VALIDATION_PATH)
        
        # Robust Index/Date Handling
        # If 'Date' or 'date' is in index, reset index to make it a column
        df = df.reset_index()
        
        # Identify the date column
        date_col = None
        for col in df.columns:
            if col.lower() == 'date':
                date_col = col
                break
        
        if not date_col:
            # Maybe index was unnamed and reset_index created 'index'
            if 'index' in df.columns:
                 date_col = 'index'
            else:
                 # Fallback, assume first column if it looks like date? 
                 # Unsafe. Let's error if not found.
                 raise ValueError("Date column not found in validation data")
        
        # Rename to 'date' for JSON consistency if needed, or use found name
        # Let's standardize to 'date'
        if date_col != 'date':
            df.rename(columns={date_col: 'date'}, inplace=True)
            
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df = df.replace({np.nan: None})
        
        data = {
            "dates": df['date'].tolist(),
            "indicators": {
                col: df[col].tolist() for col in df.columns if col != 'date'
            }
        }
        return JSONResponse(content=data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading validation data: {e}")
