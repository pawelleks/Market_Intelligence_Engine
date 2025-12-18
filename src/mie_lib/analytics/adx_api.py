
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

# Reuse the calculation logic
from mie_lib.analytics.adx_dmi import calculate_adx

router = APIRouter()

RAW_DIR = Path("data/raw")

@router.get("/api/v1/analytics/adx/{ticker}")
def get_adx_report(ticker: str) -> JSONResponse:
    """
    Returns data for the ADX Trend Strength Report page:
    - Latest Status (Computed on fly)
    - Historical Data for Charting (Price + ADX/DI)
    """
    ticker = ticker.upper()
    raw_path = RAW_DIR / f"{ticker}.parquet"
    
    if not raw_path.exists():
         raise HTTPException(status_code=404, detail=f"Raw data not found for {ticker}")
            
    try:
        # 1. Load Raw Data
        df = pd.read_parquet(raw_path)
        required = ['date', 'high', 'low', 'close']
        if not all(c in df.columns for c in required):
             df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)
             
        df.sort_values('date', inplace=True)
        
        # 2. Calculate ADX (Full History)
        df_adx = calculate_adx(df, period=14)
        
        # 3. Prepare History (Last ~2 Years / 500 rows for display)
        # Prompt said "Load the last 1-2 years"
        
        df_subset = df_adx.tail(500).copy()
        
        # Format Date
        if "date" in df_subset.columns:
            df_subset["date"] = df_subset["date"].dt.strftime("%Y-%m-%d")
            
        columns_to_keep = ["date", "close", "adx", "plus_di", "minus_di"]
        # Ensure they exist (calculating on short history might result in NaNs/missing cols if calc failed)
        available_cols = df_subset.columns.tolist()
        final_cols = [c for c in columns_to_keep if c in available_cols]
        
        df_subset = df_subset[final_cols].replace({np.nan: None})
        history = df_subset.to_dict(orient="records")
        
        # 4. Prepare Latest Status
        latest_status = {}
        if len(df_adx) >= 2:
            last_row = df_adx.iloc[-1]
            prev_row = df_adx.iloc[-2]
            
            cur_adx = last_row.get('adx', np.nan)
            cur_pdi = last_row.get('plus_di', np.nan)
            cur_mdi = last_row.get('minus_di', np.nan)
            prev_adx = prev_row.get('adx', np.nan)
            
            if pd.notna(cur_adx) and pd.notna(cur_pdi) and pd.notna(cur_mdi):
                latest_status = {
                    "adx": float(cur_adx),
                    "plus_di": float(cur_pdi),
                    "minus_di": float(cur_mdi),
                    "is_adx_strong": bool(cur_adx > 25),
                    "is_adx_uptrend": bool(cur_pdi > cur_mdi),
                    "is_adx_accelerating": bool(cur_adx > prev_adx) if pd.notna(prev_adx) else False
                }

        return JSONResponse(content={
            "ticker": ticker,
            "latest": latest_status,
            "history": history
        })

    except Exception as e:
        print(f"Error generating ADX report for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating ADX report: {e}")
