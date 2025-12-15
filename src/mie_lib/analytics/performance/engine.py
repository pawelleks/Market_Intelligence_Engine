"""
Market Performance Calculation Engine.

Calculates multi-period returns and 52-week price context for a list of tickers.
"""
import pandas as pd
import numpy as np
from datetime import date
from typing import List, Dict, Any, Optional

from mie_lib.analytics.tsmom.data_loader import load_all_tickers_ohlc

# Trading days approximations
PERIODS = {
    "1d": 1,
    "1w": 5,
    "1m": 21,
    "3m": 63,
    "6m": 126,
    "1y": 252
}

def calculate_performance_snapshot(tickers: List[str]) -> List[Dict[str, Any]]:
    """
    Calculates performance metrics for the given list of tickers.
    Returns a list of dictionaries suitable for API response.
    """
    # 1. Load Data
    data_map = load_all_tickers_ohlc(tickers)
    results = []

    for ticker, df in data_map.items():
        if df.empty or len(df) < 2:
            continue

        try:
            # Get latest price
            current_price = df["price"].iloc[-1]
            last_date = df.index[-1].date()
            
            # Calculate Returns
            metrics = {
                "ticker": ticker,
                "price": current_price,
                "asof_date": last_date,
                # Default nulls
                "ret_1d": None,
                "ret_1w": None,
                "ret_1m": None,
                "ret_3m": None,
                "ret_6m": None,
                "ret_1y": None,
                "high_52w": None,
                "low_52w": None,
                "pct_52w": None # 0.0 to 1.0 (0% at low, 100% at high)
            }

            # Helper for return calc
            def get_ret(days):
                if len(df) > days:
                    prev_price = df["price"].iloc[-(days + 1)]
                    return (current_price / prev_price) - 1
                return None

            metrics["ret_1d"] = get_ret(PERIODS["1d"])
            metrics["ret_1w"] = get_ret(PERIODS["1w"])
            metrics["ret_1m"] = get_ret(PERIODS["1m"])
            metrics["ret_3m"] = get_ret(PERIODS["3m"])
            metrics["ret_6m"] = get_ret(PERIODS["6m"])
            metrics["ret_1y"] = get_ret(PERIODS["1y"])

            # 52-Week Range
            # Look back 252 days (or available history if less)
            lookback = PERIODS["1y"]
            start_idx = max(0, len(df) - lookback)
            recent_df = df.iloc[start_idx:]
            
            # Use High/Low columns if available, else Price
            # Typically OHLC has high/low. Fallback to price.
            if "high" in recent_df.columns and "low" in recent_df.columns:
                high_52w = recent_df["high"].max()
                low_52w = recent_df["low"].min()
            else:
                high_52w = recent_df["price"].max()
                low_52w = recent_df["price"].min()

            metrics["high_52w"] = high_52w
            metrics["low_52w"] = low_52w
            
            # Position in Range (0.0 - 1.0)
            if high_52w > low_52w:
                metrics["pct_52w"] = (current_price - low_52w) / (high_52w - low_52w)
            else:
                metrics["pct_52w"] = 0.5 # Flat/Unknown

            results.append(metrics)

        except Exception as e:
            # Log error but continue
            print(f"Error calculating performance for {ticker}: {e}")
            continue

    return results
