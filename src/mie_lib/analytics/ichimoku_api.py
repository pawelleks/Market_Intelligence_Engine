
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from mie_lib.analytics.ichimoku import calculate_ichimoku
from mie_lib.utils.paths import DATA_DIR

router = APIRouter(prefix="/api/v1/analytics/trend", tags=["analytics"])

@router.get("/ichimoku/{ticker}")
def get_ichimoku_data(ticker: str) -> JSONResponse:
    """
    Returns Ichimoku Kinko Hyo analysis for a ticker.
    Includes:
    - Verdict (Strong Bullish, Neutral, Bearish)
    - Latest Flags
    - Time Series Data (Last 200 Days) for Charting
    """
    ticker = ticker.upper()
    try:
        # 1. Load Data
        path = DATA_DIR / "raw" / f"{ticker}.parquet"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
            
        df = pd.read_parquet(path)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Data empty for {ticker}")

        # 2. Calculate Indicators
        # Sort and reset index
        df = df.sort_values("date").reset_index(drop=True)
        df = calculate_ichimoku(df)
        
        # 3. Analyze Latest State
        # We need the latest VALID row for price, but Span A/B might differ due to shift logic?
        # Span A/B are shifted forward.
        # At index t (today), 'senkou_span_a' contains the value derived from t-26, plotted at t.
        # So we just take the row at index -1.
        
        latest = df.iloc[-1]
        close = float(latest["close"])
        span_a = float(latest["senkou_span_a"]) if pd.notna(latest["senkou_span_a"]) else None
        span_b = float(latest["senkou_span_b"]) if pd.notna(latest["senkou_span_b"]) else None
        
        # Check Chikou
        # Logic: Is today's close > price 26 days ago?
        is_chikou_confirmed = False
        if len(df) > 26:
            price_26_ago = float(df.iloc[-27]["close"])
            if pd.notna(close) and pd.notna(price_26_ago):
                is_chikou_confirmed = close > price_26_ago
                
        # Flags
        is_above_cloud = False
        if span_a is not None and span_b is not None:
            max_span = max(span_a, span_b)
            min_span = min(span_a, span_b)
            is_above_cloud = close > max_span
            
        is_cloud_green = False
        if span_a is not None and span_b is not None:
            is_cloud_green = span_a > span_b
            
        # Verdict Logic
        verdict = "NEUTRAL"
        reason = "Price is within the Cloud or signals are mixed."
        
        if is_above_cloud and is_cloud_green and is_chikou_confirmed:
            verdict = "STRONG BULLISH"
            reason = "Price above Cloud, Cloud is Green, and Chikou Span confirms trend."
        elif span_a is not None and span_b is not None and close < min_span:
            verdict = "BEARISH"
            reason = "Price is below the Cloud."
        # Else remains NEUTRAL (Inside Cloud)
        
        # 4. Prepare Series Data (Last 200 Days)
        # We need date, open, high, low, close, and all ichimoku lines
        # Replace NaN with None
        output_df = df.tail(200).copy()
        
        # Add Chikou Span for plotting at T-26?
        # Users usually expect Chikou to be sent as a separate line or just the Close line shifted.
        # The prompt says: "Plot the Chikou Span (Lagging Line) shifted 26 periods back."
        # This is a visualization concern. We send the current Close as "chikou_span" but the frontend needs to handle the shift?
        # Or should we send the data shifted?
        # If we send a time series, "chikou_span" at date D should represent the Chikou value PLOTTED at date D.
        # The Chikou value plotted at D is the Close from D+26.
        # So `chikou_span` column = `close`.shift(-26)
        # Let's add that column explicitly for easy plotting.
        output_df["chikou_plotted"] = output_df["close"].shift(-26)
        
        # Wait, if we are at the end of the series (Latest), we don't know the future Close.
        # So Chikou ends 26 periods ago.
        # The prompt says "Plot the Chikou Span... shifted 26 periods back".
        # Standard: Today's Close is plotted 26 days ago.
        # So at Date=Today, Chikou is NaN (it will be plotted 26 days in future? No).
        # At Date=Today-26, Chikou is Today's Close.
        # So the `chikou_plotted` column should be correct: `close.shift(-26)`.
        
        output_df = output_df.replace({np.nan: None})
        
        if "date" in output_df.columns:
            output_df["date"] = output_df["date"].dt.strftime("%Y-%m-%d")
            
        series = output_df[[
            "date", "open", "high", "low", "close", 
            "tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b", "chikou_plotted"
        ]].to_dict(orient="records")
        
        return JSONResponse(content={
            "ticker": ticker,
            "verdict": {
                "status": verdict,
                "reason": reason,
                "flags": {
                    "is_above_cloud": is_above_cloud,
                    "is_cloud_green": is_cloud_green,
                    "is_chikou_confirmed": is_chikou_confirmed
                }
            },
            "series": series
        })

    except Exception as e:
        print(f"Error in Ichimoku API: {e}")
        raise HTTPException(status_code=500, detail=str(e))
