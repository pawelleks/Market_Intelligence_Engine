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
                "ret_ytd": None,
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

            # YTD Calculation
            current_year = df.index[-1].year
            prev_year_mask = df.index.year < current_year
            
            # If we have data from previous years, use the last close of previous year
            if prev_year_mask.any():
                base_price = df.loc[prev_year_mask, "price"].iloc[-1]
                metrics["ret_ytd"] = (current_price / base_price) - 1
            else:
                # If listed this year, use the first available price
                base_price = df["price"].iloc[0]
                metrics["ret_ytd"] = (current_price / base_price) - 1

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


def calculate_sector_history(tickers: List[str], window_days: int = 252) -> Dict[str, Any]:
    """
    Returns historical cumulative performance for the given list of tickers.
    :param tickers: List of ticker symbols
    :param window_days: Number of trading days to include (default 1 year ~ 252)
    :return: Dictionary with:
             - dates: List of date strings
             - series: Dictionary of {ticker: [list of cumulative ret values]}
    """
    data_map = load_all_tickers_ohlc(tickers)
    
    # Identify common date index intersection to align all series
    # Or align to the longest and forward fill? Intersection is safer for plotting.
    # Let's align to the Union of dates, but drop days where SPY (benchmark) is missing?
    # Simpler: Align to the most recent window_days of the first ticker (usually SPY or robust one)
    
    # 1. Find the union of dates for the window
    # Actually, we want to align everything.
    # Convert map to DataFrame
    price_df = pd.DataFrame()
    
    for ticker, df in data_map.items():
        if df.empty: continue
        # Rename price column
        col_name = ticker.upper()
        # Take last N days + buffer for rolling calc?
        # User wants "1 Year Chart" (Cumulative) and "12M Rolling" (Need 2 years data for 1Y of 12M rolling)
        # Let's fetch 2 years to be safe.
        df_subset = df[["price"]].rename(columns={"price": col_name})
        price_df = pd.concat([price_df, df_subset], axis=1)
        
    price_df.sort_index(inplace=True)
    
    # Filter for last N days (approx 2 years = 504 days for rolling charts)
    limit = window_days * 2 
    if len(price_df) > limit:
        price_df = price_df.iloc[-limit:]
        
    # Fill NAs? Forward fill valid for prices
    price_df.ffill(inplace=True)
    price_df.dropna(how='all', inplace=True) # Drop days with NO data

    # 2. Calculate Metrics
    # A. 1 Year Normalized (Cumulative)
    # Start date = 1 year ago (approx 252 days)
    # Slice last 252 points
    lookback_1y = min(len(price_df), 252)
    df_1y = price_df.iloc[-lookback_1y:].copy()
    
    # Normalize to start at 0%
    normalized_1y = {}
    for col in df_1y.columns:
        start_price = df_1y[col].iloc[0]
        if pd.isna(start_price) or start_price == 0:
            normalized_1y[col] = []
        else:
            # (P_t / P_0) - 1
            normalized_1y[col] = ((df_1y[col] / start_price) - 1).tolist()
            
    dates_1y = [d.strftime("%Y-%m-%d") for d in df_1y.index]
    
    # B. 12-Month Rolling Return
    # For each day in the last 1 year, calculate return over PREVIOUS 1 year (252 days)
    # Rolling window = 252
    rolling_12m = {}
    
    # Calculate % change over 252 days
    # This requires 2 years of data.
    # We use 'price_df' which ideally has 504 days.
    # rolling_ret = price_df.pct_change(periods=252)
    # Then take the last 252 days of that result for plotting?
    # No, we want the chart to cover the last 1 year.
    # So we plot values for T=Today... T=Today-1Y.
    # The value at T is Ret(T, T-1Y).
    
    rolling_df = price_df.pct_change(periods=252)
    df_rolling_plot = rolling_df.iloc[-lookback_1y:].copy()
    
    for col in df_rolling_plot.columns:
        # Handle NaNs
        rolling_12m[col] = df_rolling_plot[col].where(pd.notnull(df_rolling_plot[col]), None).tolist()

    return {
        "dates": dates_1y,
        "normalized_1y": normalized_1y,
        "rolling_12m": rolling_12m
    }


def calculate_sector_correlations(tickers: List[str]) -> Dict[str, Any]:
    """
    Calculates 2 correlation matrices:
    1. Last Calendar Year (Jan 1 - Dec 31 of n-1)
    2. Rolling 12 Months (Last 252 trading days)
    """
    data_map = load_all_tickers_ohlc(tickers)
    
    # Align Data
    price_df = pd.DataFrame()
    for ticker, df in data_map.items():
        if df.empty: continue
        col_name = ticker.upper()
        # Need enough history for "Last Year" + "Rolling 12M"
        # 2 years is safe.
        df_subset = df[["price"]].rename(columns={"price": col_name})
        price_df = pd.concat([price_df, df_subset], axis=1)
        
    price_df.sort_index(inplace=True)
    price_df.ffill(inplace=True)
    price_df.dropna(how='all', inplace=True)
    
    # Calculate Returns (for correlation)
    # Using Daily Returns
    rets_df = price_df.pct_change().dropna()
    
    if rets_df.empty:
        return {"calendar_year": {}, "rolling_12m": {}}

    # 1. Rolling 12 Months (Last 252 days)
    lookback = min(len(rets_df), 252)
    rets_rolling = rets_df.iloc[-lookback:]
    corr_rolling = rets_rolling.corr().round(2)
    
    # 2. Last Calendar Year
    # Determine "Last Year"
    last_date = rets_df.index[-1]
    current_year = last_date.year
    # If we are in Jan 2026, Last Year is 2025.
    target_year = current_year - 1
    
    # Filter for that year
    rets_calendar = rets_df[rets_df.index.year == target_year]
    
    if rets_calendar.empty:
        # Fallback if no data for last year (e.g. fresh year start or short history)
        corr_calendar = pd.DataFrame() 
    else:
        corr_calendar = rets_calendar.corr().round(2)

    # Helper to convert DF to JSON-friendly dict
    def to_matrix(df_corr):
        if df_corr.empty: return {"tickers": [], "matrix": []}
        cols = df_corr.columns.tolist()
        # Matrix as list of lists? Or list of objects?
        # Recharts heatmap usually needs x, y, value.
        # But a custom grid is easier with a 2D array.
        matrix = []
        for r in cols:
            row_data = []
            for c in cols:
                val = df_corr.loc[r, c]
                row_data.append(val if not pd.isna(val) else 0)
            matrix.append(row_data)
        return {"tickers": cols, "matrix": matrix}

    return {
        "calendar_year": to_matrix(corr_calendar),
        "rolling_12m": to_matrix(corr_rolling),
        "year_label": str(target_year)
    }

