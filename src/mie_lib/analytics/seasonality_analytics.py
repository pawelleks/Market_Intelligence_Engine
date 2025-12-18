import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Define base path relative to project root
SEASONALITY_BASE_DIR = Path("data/seasonality/base")

def _load_base_data(ticker: str) -> pd.DataFrame:
    path = SEASONALITY_BASE_DIR / f"{ticker}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Seasonality base data not found for {ticker}")
    return pd.read_parquet(path)

def get_seasonal_curves(ticker: str, lookbacks: List[int]) -> Dict[str, Any]:
    """
    Computes cumulative return curves for current year vs history.
    Returns daily returns ('r') for frontend accumulation.
    """
    try:
        df = _load_base_data(ticker)
    except FileNotFoundError:
        # Return structure with empty data if file missing
        return {"ticker": ticker, "current_year": 0, "current_path": {"label": "N/A", "data": []}, "curves": []}

    current_year = int(df['year'].max())
    
    # 1. Current Year Path
    # Use 'doy_trading' column from base file
    current_df = df[df['year'] == current_year].sort_values('doy_trading')
    current_path = {
        "label": f"Current ({current_year})",
        # Rename to 'tdoy' for frontend compatibility
        "data": current_df[['doy_trading', 'r']].rename(columns={'doy_trading': 'tdoy'}).to_dict(orient='records')
    }
    
    # 2. Historical Average Curves
    curves = []
    for lookback in lookbacks:
        start_year = current_year - lookback
        # Filter: within lookback window AND strictly before current year
        hist_df = df[(df['year'] >= start_year) & (df['year'] < current_year)]
        
        if hist_df.empty:
            continue
            
        # Group by Trading Day of Year using 'doy_trading'
        avg_daily_ret = hist_df.groupby('doy_trading')['r'].mean().reset_index()
        
        # Rename to 'tdoy' for frontend
        avg_daily_ret = avg_daily_ret.rename(columns={'doy_trading': 'tdoy'})
        
        curves.append({
            "label": f"{lookback}-Year Avg",
            "data": avg_daily_ret.to_dict(orient='records')
        })
        
    return {
        "ticker": ticker,
        "current_year": current_year,
        "current_path": current_path,
        "curves": curves
    }

def get_calendar_heatmap(ticker: str, lookback_years: int) -> Dict[str, Any]:
    """
    Computes 12x31 matrix of average returns.
    """
    try:
        df = _load_base_data(ticker)
    except FileNotFoundError:
        return {"heatmap": []}

    current_year = int(df['year'].max())
    start_year = current_year - lookback_years
    
    # Filter: within lookback window AND strictly before current year
    hist_df = df[(df['year'] >= start_year) & (df['year'] < current_year)]
    
    if hist_df.empty:
        return {"heatmap": []}
        
    # Group by Month and Day, calculate Mean Return, convert to %
    heatmap_df = hist_df.groupby(['month', 'day'])['r'].mean() * 100
    
    heatmap_data = []
    for (month, day), val in heatmap_df.items():
        heatmap_data.append({
            "month": int(month),
            "day": int(day),
            "value": float(round(val, 2))
        })
        
    return {
        "ticker": ticker,
        "lookback_years": lookback_years,
        "heatmap": heatmap_data
    }

def get_day_drilldown(ticker: str, month: int, day: int, lookback_years: int) -> Dict[str, Any]:
    """
    Fetches historical records for a specific calendar day.
    """
    try:
        df = _load_base_data(ticker)
    except FileNotFoundError:
        return {"stats": {}, "records": []}

    current_year = int(df['year'].max())
    start_year = current_year - lookback_years
    
    # Filter for specific day within lookback (excluding current year)
    day_df = df[
        (df['month'] == month) & 
        (df['day'] == day) & 
        (df['year'] >= start_year) &
        (df['year'] < current_year)
    ].copy()
    
    if day_df.empty:
        return {
            "month": month, 
            "day": day, 
            "stats": {"count": 0, "mean": 0, "win_rate": 0}, 
            "records": []
        }
        
    day_df['r_pct'] = day_df['r'] * 100
    
    stats = {
        "count": int(len(day_df)),
        "mean": float(day_df['r_pct'].mean()),
        "median": float(day_df['r_pct'].median()),
        "win_rate": float((day_df['r_pct'] > 0).mean() * 100),
        "best": float(day_df['r_pct'].max()),
        "worst": float(day_df['r_pct'].min())
    }
    
    # Sort by year descending
    records = day_df[['year', 'date', 'r_pct', 'close']].sort_values('year', ascending=False).copy()
    
    # Format date
    records['date'] = records['date'].dt.strftime('%Y-%m-%d')
    
    return {
        "month": month,
        "day": day,
        "stats": stats,
        "records": records.to_dict(orient='records')
    }
