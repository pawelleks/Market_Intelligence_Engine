import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple

# We rely on the features parquet containing date, close, adj_close (for SMA calcs), high, and low

# --- MOVING AVERAGE CALCULATION ---

def _calculate_smas(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates 50, 150, and 200-day Simple Moving Averages."""
    
    if df.empty or len(df) < 200:
        return df # Not enough data for the long-term MAs

    df = df.copy()
    
    # Use adj_close as the source for MAs for accurate plotting/calculation
    price_col = 'adj_close' if 'adj_close' in df.columns else 'close'
    if price_col not in df.columns:
        raise ValueError("Price column (adj_close or close) is missing for SMA calculation.")

    df['SMA_50'] = df[price_col].rolling(window=50).mean()
    df['SMA_150'] = df[price_col].rolling(window=150).mean()
    df['SMA_200'] = df[price_col].rolling(window=200).mean()
    
    return df

# --- TREND TEMPLATE CHECKS ---

def run_minervini_template(df_full: pd.DataFrame, check_date: date) -> Dict[str, Any]:
    """Runs the 10-point Minervini Trend Template technical checks on the last available day."""

    # 1. Prepare and filter data up to the check date
    df_full['date'] = pd.to_datetime(df_full['date']).dt.date
    df = df_full[df_full['date'] <= check_date].copy()
    
    # Calculate MAs only on the required historical data
    df = _calculate_smas(df)

    # Get the data for the last available day (the day we check the template)
    last_row = df.iloc[-1]
    
    # Ensure MAs are calculated
    if pd.isna(last_row['SMA_200']):
        return {"status": "FAIL", "summary": "Insufficient data to calculate long-term MAs (need > 200 days).", "checks": []}

    # Use the current price
    current_price = last_row['close']
    
    # Calculate 52-week High/Low relative to the check date
    lookback_year_ago = check_date - timedelta(days=365)
    df_52w = df[df['date'] >= lookback_year_ago]
    
    low_52w = df_52w['low'].min()
    high_52w = df_52w['high'].max()

    # Determine 200-day SMA trend: check if 200 SMA 1 month ago is lower than today's 200 SMA
    last_200_sma = last_row['SMA_200']
    
    month_ago_date = check_date - timedelta(days=30)
    # Handle case where month_ago_date might not exist in df (e.g. weekend/holiday)
    # We take the last available data point on or before month_ago_date
    month_ago_df = df[df['date'] <= month_ago_date]
    if month_ago_df.empty:
         # Fallback if data is extremely sparse, though unlikely with >200 days check
         month_ago_200_sma = last_200_sma 
    else:
        month_ago_200_sma = month_ago_df['SMA_200'].iloc[-1]
    
    # CHECKLIST EXECUTION
    checks = {
        # Check 1: Current price > 150-day SMA AND Current price > 200-day SMA
        "P_GT_MA": (current_price > last_row['SMA_150']) and (current_price > last_row['SMA_200']),
        
        # Check 2: 150-day SMA > 200-day SMA
        "MA_150_GT_200": last_row['SMA_150'] > last_row['SMA_200'],
        
        # Check 3: 200-day SMA is trending up (200 SMA today > 200 SMA 1 month ago)
        "MA_200_RISING": last_200_sma > month_ago_200_sma,
        
        # Check 4: 50-day SMA > 150-day SMA AND 50-day SMA > 200-day SMA
        "MA_50_GT_LONG": (last_row['SMA_50'] > last_row['SMA_150']) and (last_row['SMA_50'] > last_row['SMA_200']),
        
        # Check 5: Current price > 50-day SMA
        "P_GT_MA_50": current_price > last_row['SMA_50'],
        
        # Check 6: Current price is within 25% of 52-week High
        "CLOSE_TO_HIGH": (high_52w > 0) and ( (high_52w - current_price) / high_52w <= 0.25 ), 
        
        # Check 7: Current price is at least 30% above 52-week Low
        "FAR_FROM_LOW": (low_52w > 0) and ( (current_price - low_52w) / low_52w >= 0.30 ), 
        
        # Checks 8-10 are volume and fundamentals, which require external data not always present here.
    }
    
    # Adapt for ETFs (SPY, QQQ): Focus only on the 7 core technical checks (Checks 1-7).
    total_technical_passes = sum(checks.values())
    
    # A conservative ETF screening rule requires 6 out of the 7 core technical checks to pass.
    is_passing = total_technical_passes >= 6 
    
    return {
        "status": "PASS" if is_passing else "FAIL",
        "total_passed": total_technical_passes,
        "required_passes": 6,
        "check_date": check_date.isoformat(),
        "current_price": float(current_price),
        "data_status": checks # checks dictionary remains the 7 technical rules
    }
