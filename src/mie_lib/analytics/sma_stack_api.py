
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

router = APIRouter()

ANALYTICS_DIR = Path("data/analytics")
FEATURES_DIR = Path("data/features")

@router.get("/api/v1/analytics/sma-stack/{ticker}")
def get_sma_stack_report(ticker: str) -> JSONResponse:
    """
    Returns data for the SMA Stack Report page:
    - Latest Status (from sma_stack_daily.parquet)
    - Historical Data for Charting (from features/{ticker}.parquet)
    """
    ticker = ticker.upper()
    
    # 1. Get Latest Status
    status_path = ANALYTICS_DIR / "sma_stack_daily.parquet"
    latest_status = {}
    
    if status_path.exists():
        try:
            df_status = pd.read_parquet(status_path)
            # Filter for ticker
            row = df_status[df_status["ticker"] == ticker]
            if not row.empty:
                # Convert to dict and handle numpy types
                record = row.iloc[0].replace({np.nan: None}).to_dict()
                if "date" in record:
                     record["date"] = record["date"].strftime("%Y-%m-%d") if pd.notna(record["date"]) else None
                latest_status = record
        except Exception as e:
            print(f"Error reading SMA stack status: {e}")
            # Non-fatal, just return empty status
            
    # 2. Get Historical Data (Price + EMAs)
    features_path = FEATURES_DIR / f"{ticker}.parquet"
    history = []
    
    if features_path.exists():
        try:
            # We need date, close, ema_20, ema_50, ema_200
            # Also might want open/high/low for candle chart if desired, but prompt said "Closing Price overlaid"
            # Let's get OHLC anyway for completeness in case we want candles.
            
            # Since features file might not have OHLC (only 'ret' or 'close'), let's check.
            # actually build_features output columns include 'close', 'adj_close' now as per my previous edit.
            # It usually doesn't have Open/High/Low unless I add them.
            # The previous 'get_price_features' endpoint merges raw data.
            # I will optimize and just read 'close' + EMAs from features for simplicity and speed,
            # as the prompt requested "Plot the closing price overlaid".
            
            cols = ["date", "close", "adj_close", "ema_20", "ema_50", "ema_200"]
            df_feat = pd.read_parquet(features_path)
            
            # Ensure columns exist
            available_cols = df_feat.columns.tolist()
            selected_cols = [c for c in cols if c in available_cols]
            
            df_subset = df_feat[selected_cols].copy()
            
            # Use adj_close as close if available (to match EMAs)
            if "adj_close" in df_subset.columns:
                df_subset["close"] = df_subset["adj_close"].fillna(df_subset["close"])
            
            # Sort and take full history 
            df_subset = df_subset.sort_values("date")
           
            # Format
            if "date" in df_subset.columns:
                df_subset["date"] = df_subset["date"].dt.strftime("%Y-%m-%d")
                
            df_subset = df_subset.replace({np.nan: None})
            
            # Keep only the fields expected by frontend (we mapped adj_close to close)
            final_cols = ["date", "close", "ema_20", "ema_50", "ema_200"]
            history = df_subset[final_cols].to_dict(orient="records")
            
        except Exception as e:
            print(f"Error reading history for {ticker}: {e}")
            raise HTTPException(status_code=500, detail=f"Error reading history: {e}")
    else:
        raise HTTPException(status_code=404, detail=f"Data not found for {ticker}")

    return JSONResponse(content={
        "ticker": ticker,
        "latest": latest_status,
        "history": history
    })
