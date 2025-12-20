from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from mie_lib.utils.paths import DATA_DIR
from mie_lib.utils.logging import get_logger

router = APIRouter()
LOG = get_logger("trend_summary_api")

class TrendSummaryRow(BaseModel):
    ticker: str
    date: Optional[str] = None
    is_ema_stacked_up: bool
    is_adx_strong_trend: bool
    is_psar_bullish: bool
    is_above_cloud: bool
    is_cloud_green: Optional[bool] = False
    dow_theory_status: str
    trend_score: int
    ema_age: int = 0
    cloud_age: int = 0

@router.get("/summary-table", response_model=List[TrendSummaryRow])
def get_trend_summary():
    """
    Aggregates trend indicators from SMA, ADX, PSAR, and Ichimoku into a single summary table.
    Calculates a Trend Score (0-4).
    """
    try:
        # Paths
        analytics_dir = DATA_DIR / "analytics"
        sma_path = analytics_dir / "sma_stack_daily.parquet"
        adx_path = analytics_dir / "adx_daily.parquet"
        psar_path = analytics_dir / "psar_daily.parquet"
        ichimoku_path = analytics_dir / "ichimoku_daily.parquet"

        # Load DataFrames
        df_sma = pd.read_parquet(sma_path) if sma_path.exists() else pd.DataFrame()
        df_adx = pd.read_parquet(adx_path) if adx_path.exists() else pd.DataFrame()
        df_psar = pd.read_parquet(psar_path) if psar_path.exists() else pd.DataFrame()
        df_ichi = pd.read_parquet(ichimoku_path) if ichimoku_path.exists() else pd.DataFrame()

        # Normalize Ticker Columns
        if not df_sma.empty and "ticker" in df_sma.columns:
            df_sma["ticker"] = df_sma["ticker"].astype(str).str.upper()
        
        if not df_adx.empty and "ticker" in df_adx.columns:
            df_adx["ticker"] = df_adx["ticker"].astype(str).str.upper()

        if not df_psar.empty:
            # PSAR has 'Ticker' capitalized
            if "Ticker" in df_psar.columns:
                df_psar.rename(columns={"Ticker": "ticker"}, inplace=True)
            if "ticker" in df_psar.columns:
                df_psar["ticker"] = df_psar["ticker"].astype(str).str.upper()
        
        if not df_ichi.empty and "ticker" in df_ichi.columns:
            df_ichi["ticker"] = df_ichi["ticker"].astype(str).str.upper()

        # Base DataFrame: Use Union of all tickers or start with SMA logic
        # Let's collect all unique tickers
        all_tickers = set()
        if not df_sma.empty: all_tickers.update(df_sma["ticker"].unique())
        if not df_adx.empty: all_tickers.update(df_adx["ticker"].unique())
        if not df_psar.empty: all_tickers.update(df_psar["ticker"].unique())
        if not df_ichi.empty: all_tickers.update(df_ichi["ticker"].unique())

        if not all_tickers:
            return []

        df_base = pd.DataFrame({"ticker": list(all_tickers)})
        
        # Merge SMA (Primary source for Date usually)
        if not df_sma.empty:
            # Keep only relevant columns
            sma_cols = ["ticker", "is_ema_stacked_up", "ema_age", "date"]
            # Check availability
            sma_cols = [c for c in sma_cols if c in df_sma.columns]
            df_base = df_base.merge(df_sma[sma_cols], on="ticker", how="left")
        
        # Merge ADX
        if not df_adx.empty:
            adx_cols = ["ticker", "is_adx_strong", "is_adx_uptrend"]
            adx_cols = [c for c in adx_cols if c in df_adx.columns]
            df_base = df_base.merge(df_adx[adx_cols], on="ticker", how="left")
            
        # Merge PSAR
        if not df_psar.empty:
            psar_cols = ["ticker", "is_psar_bullish"]
            psar_cols = [c for c in psar_cols if c in df_psar.columns]
            df_base = df_base.merge(df_psar[psar_cols], on="ticker", how="left")
            
        # Merge Ichimoku
        if not df_ichi.empty:
            ichi_cols = ["ticker", "is_above_cloud", "is_cloud_green", "cloud_age"]
            ichi_cols = [c for c in ichi_cols if c in df_ichi.columns]
            df_base = df_base.merge(df_ichi[ichi_cols], on="ticker", how="left")

        # Fill NaNs with False for bools
        bool_cols = ["is_ema_stacked_up", "is_adx_strong", "is_adx_uptrend", "is_psar_bullish", "is_above_cloud", "is_cloud_green"]
        for col in bool_cols:
            if col not in df_base.columns:
                df_base[col] = False
            else:
                df_base[col] = df_base[col].fillna(False).astype(bool)

        # Calculate Score
        # 1. EMA Stacked Up
        s1 = df_base["is_ema_stacked_up"].astype(int)
        
        # 2. ADX Strong Bullish (Strong AND Uptrend)
        s2 = (df_base["is_adx_strong"] & df_base["is_adx_uptrend"]).astype(int)
        
        # 3. PSAR Bullish
        s3 = df_base["is_psar_bullish"].astype(int)
        
        # 4. Ichimoku Above Cloud
        s4 = df_base["is_above_cloud"].astype(int)
        
        df_base["trend_score"] = s1 + s2 + s3 + s4
        
        # Columns for response
        df_base["is_adx_strong_trend"] = df_base["is_adx_strong"] & df_base["is_adx_uptrend"]
        df_base["dow_theory_status"] = "PENDING"
        
        # Format Date
        if "date" in df_base.columns:
            df_base["date"] = pd.to_datetime(df_base["date"]).dt.strftime("%Y-%m-%d").fillna("")
        else:
            df_base["date"] = None

        # Select Output
        out_cols = [
            "ticker", 
            "date",
            "is_ema_stacked_up", 
            "is_adx_strong_trend", 
            "is_psar_bullish", 
            "is_above_cloud",
            "is_cloud_green", 
            "dow_theory_status", 
            "trend_score",
            "ema_age",
            "cloud_age"
        ]
        
        # Fill missing ages
        if "ema_age" not in df_base.columns: df_base["ema_age"] = 0
        if "cloud_age" not in df_base.columns: df_base["cloud_age"] = 0
        
        df_base["ema_age"] = df_base["ema_age"].fillna(0).astype(int)
        df_base["cloud_age"] = df_base["cloud_age"].fillna(0).astype(int)
        
        return df_base[out_cols].to_dict(orient="records")

    except Exception as e:
        LOG.error(f"Failed to generate trend summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
