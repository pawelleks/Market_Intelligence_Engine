
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
import logging
from typing import List, Optional
from pydantic import BaseModel

from mie_lib.utils.paths import DATA_DIR, RAW_DIR
from mie_lib.utils.logging import get_logger
from mie_lib.analytics.volatility import calculate_atr, calculate_volatility_metrics, get_volatility_regime

router = APIRouter()
LOG = get_logger("volatility_api")

class VolatilityRow(BaseModel):
    ticker: str
    date: Optional[str] = None
    atr: Optional[float] = None
    atr_rank: Optional[float] = None
    atr_percent: Optional[float] = None
    volatility_regime: Optional[str] = None
    volatility_desc: Optional[str] = None

@router.get("/api/v1/volatility/summary", response_model=List[VolatilityRow], tags=["volatility"])
def get_volatility_summary():
    """
    Returns the latest daily volatility metrics for all tickers.
    """
    try:
        path = DATA_DIR / "analytics" / "volatility_daily.parquet"
        
        if not path.exists():
            return []
            
        df = pd.read_parquet(path)
        
        if df.empty:
            return []
            
        # Normalize headers
        df.columns = [c.lower() for c in df.columns]
        
        # Ensure Ticker is Upper
        if "ticker" in df.columns:
            df["ticker"] = df["ticker"].astype(str).str.upper()
            
        # Format Date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d").fillna("")
            
        # Replace NaN with None
        df = df.replace({np.nan: None})
        
        return df.to_dict(orient="records")
        
    except Exception as e:
        LOG.error(f"Failed to fetch volatility summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/volatility/history/{ticker}", tags=["volatility"])
def get_volatility_history(ticker: str):
    """
    Returns historical volatility (ATR, Rank, Regime) for a specific ticker.
    Calculates on-the-fly from raw daily data.
    """
    try:
        ticker = ticker.upper()
        raw_path = RAW_DIR / f"{ticker}.parquet"
        
        if not raw_path.exists():
            raise HTTPException(status_code=404, detail=f"Raw data not found for {ticker}")
            
        df = pd.read_parquet(raw_path)
        
        # Normalize columns
        df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)
        
        if df.empty:
            return []
            
        df.sort_values('date', inplace=True)
        
        # Calculate Metrics
        df = calculate_atr(df, period=14)
        df = calculate_volatility_metrics(df, lookback_days=126)
        
        # Add Regime Column (row-by-row)
        # Note: applying row-by-row is slow for large DF, but ok for single ticker history (few thousand rows)
        # Optimization: Vectorize or simple loop
        regimes = []
        descs = []
        
        # We need prev_row. Shift df.
        df['prev_close'] = df['close'].shift(1)
        df['prev_atr'] = df['atr'].shift(1)
        
        # Vectorized Regime Logic attempt?
        # get_volatility_regime uses complex logic strings. Let's map it.
        # Ideally, we return just the values and let frontend decide text, but for consistency we can compute here.
        # Let's simple loop for now, it's safer logic preservation.
        
        # Prune nan start
        df_clean = df.dropna(subset=['atr', 'atr_rank']).copy()
        
        results = []
        # Convert to dicts for iteration
        records = df_clean.to_dict('records')
        
        # We need to peek at 'previous' relative to the original DF sequence
        # But 'df_clean' might have gaps if we dropped NaNs. 
        # Actually, df has contiguous dates usually.
        # Let's just iterate the full df to keep index alignment for 'prev'.
        
        # Re-approach: Vectorize the conditions
        # 1. Squeeze: Rank < 20
        # 2. Expansion: Rank > 80
        # 3. Trend: Close > PrevClose & ATR > PrevATR & Rank > 50
        
        df['regime'] = "Neutral"
        
        # Squeeze
        df.loc[df['atr_rank'] < 20, 'regime'] = "Squeeze"
        
        # Expansion
        df.loc[df['atr_rank'] > 80, 'regime'] = "Expansion"
        
        # Trend Strength
        # Close > PrevClose AND ATR > PrevATR AND Rank > 50
        trend_mask = (
            (df['close'] > df['prev_close']) & 
            (df['atr'] > df['prev_atr']) & 
            (df['atr_rank'] > 50)
        )
        df.loc[trend_mask, 'regime'] = "Trend Strength"
        
        # Format for output
        out_df = df[['date', 'close', 'atr', 'atr_rank', 'atr_percent', 'regime']].copy()
        out_df['date'] = pd.to_datetime(out_df['date']).dt.strftime("%Y-%m-%d")
        out_df = out_df.replace({np.nan: None})
        
        return out_df.to_dict(orient="records")
        
    except HTTPException as he:
        raise he
    except Exception as e:
        LOG.error(f"Failed to fetch volatility history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
