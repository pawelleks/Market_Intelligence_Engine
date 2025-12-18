
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

from mie_lib.analytics.psar import calculate_psar

router = APIRouter()

RAW_DIR = Path("data/raw")

@router.get("/api/v1/analytics/psar/{ticker}")
def get_psar_report(ticker: str) -> JSONResponse:
    """
    Returns data for the PSAR Momentum Report:
    - Latest Status (Bullish/Bearish, Value)
    - Historical Data for Charting (Price + PSAR)
    """
    ticker = ticker.upper()
    raw_path = RAW_DIR / f"{ticker}.parquet"
    
    if not raw_path.exists():
         raise HTTPException(status_code=404, detail=f"Raw data not found for {ticker}")
            
    try:
        # 1. Load Raw Data
        df = pd.read_parquet(raw_path)
        required = ['date', 'high', 'low', 'close', 'open']
        # Standardize columns
        df.columns = [c.lower() for c in df.columns]
        
        if not all(c in df.columns for c in required):
             raise HTTPException(status_code=500, detail=f"Data missing required columns: {required}")
             
        df = df.sort_values('date').reset_index(drop=True)
        
        # 2. Calculate PSAR (Full History)
        # Convert to numpy for calc
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        
        psar_df = calculate_psar(highs, lows, closes)
        df["psar"] = psar_df["psar"]
        # df["psar_trend"] = psar_df["psar_trend"] # Optional if we need it
        
        # 3. Prepare History (Last ~2 Years for display/calc context)
        # Filter last 2 years for response payload size
        start_date_filter = datetime.now() - timedelta(days=730)
        df_subset = df[df["date"] >= start_date_filter].copy()
        df_subset = df_subset.reset_index(drop=True)
        
        # Format Date
        if "date" in df_subset.columns:
            df_subset["date"] = df_subset["date"].dt.strftime("%Y-%m-%d")
            
        columns_to_keep = ["date", "open", "high", "low", "close", "psar"]
        df_subset = df_subset[columns_to_keep].replace({np.nan: None})
        history = df_subset.to_dict(orient="records")
        
        # 4. Prepare Latest Status
        latest_status = {}
        if not df.empty:
            last_row = df.iloc[-1]
            
            psar_val = last_row["psar"]
            close_val = last_row["close"]
            
            # Logic: Bullish if Close > PSAR
            is_bullish = bool(close_val > psar_val)
            
            latest_status = {
                "date": last_row["date"].strftime("%Y-%m-%d"),
                "close": float(close_val),
                "psar": float(psar_val),
                "is_bullish": is_bullish
            }

        return JSONResponse(content={
            "ticker": ticker,
            "latest": latest_status,
            "history": history
        })

    except Exception as e:
        print(f"Error generating PSAR report for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating PSAR report: {e}")
