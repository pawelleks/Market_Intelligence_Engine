"""
Parabolic SAR (Stop and Reverse) calculation and storage.

This module provides:
1. `calculate_psar`: Numpy-based calculation of PSAR.
2. `calculate_and_save_psar`: Orchestrator to compute PSAR for all tickers and save daily snapshot.
"""
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

from mie_lib.utils.logging import get_logger
from mie_lib.data_ingest.yfinance_loader import read_tickers

LOG = get_logger("analytics.psar")
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
ANALYTICS_DIR = DATA_DIR / "analytics"


def calculate_psar(
    high: np.ndarray, 
    low: np.ndarray, 
    close: np.ndarray, 
    step: float = 0.02, 
    max_step: float = 0.20
) -> pd.DataFrame:
    """
    Calculate Parabolic SAR.
    
    Rules (standard Wilder):
    - Initial SAR is the first previous extreme point (EP). 
      We'll assume the first trend based on first two bars if not provided, 
      but for simplicity establishing direction by first bar > second or vice versa.
    - If trend is Long:
      - PSAR cannot be above the prior period's Low or the current period's Low. -> Actually rule is: PSAR cannot be above prior period's Low or prior-prior period's Low.
    - If trend is Short:
      - PSAR cannot be below the prior period's High or prior-prior period's High.
      
    Returns a DataFrame with columns: ['psar', 'trend']
    trend: 1 for Bullish, -1 for Bearish
    """
    n = len(close)
    psar = np.zeros(n)
    trend = np.zeros(n, dtype=int)
    ep = np.zeros(n)
    af = np.zeros(n)
    
    if n < 2:
        return pd.DataFrame({"psar": psar, "trend": trend}, index=pd.RangeIndex(n))

    # Initialize
    # Assume first trend direction based on comparison of 0 and 1
    # This is a basic initialization standard. 
    # If High[1] > High[0] -> Uptrend? Or Close[1] > Close[0]?
    # Common way: use first bar. 
    # But usually need "previous" values. Let's start calculation from index 1 (2nd bar).
    
    # Simple init: 
    # If Close[0] > Open[0] -> Bullish, else Bearish (arbitrary but self-corrects)
    # Let's use High/Low for trend assumption.
    
    # We will iterate. Numba would be faster but we use numpy loops or just python loop with numpy arrays.
    # Since we need values from T-1, a loop is inevitable without numba. 
    # Python loop is fine for daily tickers (<10k rows usually).
    
    # Variables for state
    curr_trend = 1 # 1: Bull, -1: Bear
    curr_psar = low[0] # initial guess
    curr_ep = high[0]
    curr_af = step
    
    # Set day 0 values
    psar[0] = curr_psar
    trend[0] = curr_trend
    ep[0] = curr_ep
    af[0] = curr_af
    
    # Better initialization:
    # Use standard: if High[1] > High[0] and Low[1] > Low[0] -> Up, else Down?
    # Let's assume Uptrend starting at Low[0], unless Low[0] > Low[1] ? 
    
    # Let's implement the loop carefully
    # Using the variant where we update for NEXT period.
    
    # Initial setup based on first bar
    # If we assume long, SAR = Low[0], EP = High[0], AF = step
    # If we assume short, SAR = High[0], EP = Low[0], AF = step
    
    # Let's look at first 2 bars to decide.
    if close[0] >= close[1]: # Going down?
         curr_trend = -1
         curr_psar = high[0] # SAR above
         curr_ep = low[0]
    else:
         curr_trend = 1
         curr_psar = low[0] # SAR below
         curr_ep = high[0]
         
    curr_af = step
    
    psar[0] = np.nan # Not valid really
    psar[1] = curr_psar
    trend[1] = curr_trend
    
    for i in range(1, n - 1): # Calculate for i+1 based on i
        curr_high = high[i]
        curr_low = low[i]
        
        # Calculate tentative SAR for tomorrow (i+1)
        next_psar = curr_psar + curr_af * (curr_ep - curr_psar)
        
        # Check for reversal
        next_trend = curr_trend
        
        if curr_trend == 1:
            # Uptrend
            if curr_low < next_psar: # Switch to Downtrend
                next_trend = -1
                next_psar = curr_ep # SAR becomes previous EP
                curr_ep = curr_low # Reset EP to today's low
                curr_af = step # Reset AF
            else:
                # Still Uptrend
                # Check for new EP
                if curr_high > curr_ep:
                    curr_ep = curr_high
                    curr_af = min(curr_af + step, max_step)
                
                # Rule: PSAR cannot be above Low[i] or Low[i-1]
                # We need Low[i-1] if i>0
                prev_low = low[i-1] if i > 0 else curr_low
                next_psar = min(next_psar, curr_low, prev_low)
                
        else:
            # Downtrend (-1)
            if curr_high > next_psar: # Switch to Uptrend
                next_trend = 1
                next_psar = curr_ep # SAR becomes previous EP
                curr_ep = curr_high # Reset EP to today's high
                curr_af = step # Reset AF
            else:
                # Still Downtrend
                # Check for new EP
                if curr_low < curr_ep:
                    curr_ep = curr_low
                    curr_af = min(curr_af + step, max_step)
                
                # Rule: PSAR cannot be below High[i] or High[i-1]
                prev_high = high[i-1] if i > 0 else curr_high
                next_psar = max(next_psar, curr_high, prev_high)
                
        # Update state for next iteration
        curr_trend = next_trend
        curr_psar = next_psar
        
        # Store for i+1
        psar[i+1] = curr_psar
        trend[i+1] = curr_trend
    
    return pd.DataFrame({
        "psar": psar,
        "psar_trend": trend
    })


def calculate_and_save_psar():
    """
    Iterate all tickers, load data, calc PSAR, and save daily snapshot.
    """
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    tickers = read_tickers()
    if not tickers:
        LOG.warning("No tickers found.")
        return

    results = []
    
    for ticker in tickers:
        try:
            p_path = RAW_DIR / f"{ticker}.parquet"
            if not p_path.exists():
                LOG.warning(f"Data not found for {ticker}")
                continue
            
            df = pd.read_parquet(p_path)
            if df.empty or len(df) < 5:
                continue
                
            # Ensure sorting
            df = df.sort_values("date").reset_index(drop=True)
            
            highs = df["high"].values
            lows = df["low"].values
            closes = df["close"].values
            
            psar_df = calculate_psar(highs, lows, closes)
            
            # Get latest values
            latest_idx = -1
            latest_date = df["date"].iloc[latest_idx]
            latest_close = closes[latest_idx]
            latest_psar = psar_df["psar"].iloc[latest_idx]
            
            # Logic: is_psar_bullish = Close > PSAR (or trend == 1)
            # Usually strict definition: Close > PSAR.
            # Our calculation ensures PSAR is 'below' if trend is 1 (mostly).
            is_bullish = bool(latest_close > latest_psar)
            
            results.append({
                "Date": latest_date,
                "Ticker": ticker,
                "PSAR_Value": float(latest_psar),
                "is_psar_bullish": is_bullish,
                "psar_trailing_stop": float(latest_psar)
            })
            
        except Exception as e:
            LOG.error(f"Error calculating PSAR for {ticker}: {e}")
            continue

    if not results:
        LOG.warning("No PSAR results generated.")
        return

    out_df = pd.DataFrame(results)
    out_path = ANALYTICS_DIR / "psar_daily.parquet"
    out_df.to_parquet(out_path, index=False)
    LOG.info(f"Saved PSAR daily analytics to {out_path} ({len(out_df)} records)")

if __name__ == "__main__":
    calculate_and_save_psar()
