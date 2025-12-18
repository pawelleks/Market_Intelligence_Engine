
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from mie_lib.utils.logging import get_logger
from mie_lib.utils.config import load_named_config
# Import generic feature builder
from mie_lib.features.build_features import build_features_for_ticker
from mie_lib.utils.paths import DATA_DIR

LOG = get_logger("sma_stack")
ANALYTICS_DIR = DATA_DIR / "analytics"

def calculate_and_save_sma_stack():
    """
    Iterates through all tickers, calculates SMA/EMA Stack status,
    and saves the daily summary to 'data/analytics/sma_stack_daily.parquet'.
    """
    # 1. Load Ticker List
    try:
        tcfg = load_named_config("ticker_list")
        tickers = tcfg.get("tickers", []) if isinstance(tcfg, dict) else []
    except Exception as e:
        LOG.error(f"Failed to load ticker list: {e}")
        return

    if not tickers:
        LOG.warning("No tickers found in config/ticker_list.yml")
        return

    results = []
    
    LOG.info(f"Starting SMA Stack calculation for {len(tickers)} tickers...")

    for ticker in tickers:
        try:
            # 2. Build/Get Features (returns dict with path)
            # Use 'update' mode to be efficient (only compute recent days if file exists)
            # lookback=200 ensures we have enough history for the EMA lags if doing full rebuild,
            # but 'update' mode usually just appends. 
            # We explicitly need checking 20 periods back, so let's ensure we have valid data.
            res = build_features_for_ticker(ticker, mode='update', lookback=30) 
            parquet_path = res.get("parquet")
            
            if not parquet_path or not Path(parquet_path).exists():
                LOG.warning(f"Feature file generation failed or missing for {ticker}")
                continue
                
            df = pd.read_parquet(parquet_path)
            
            if df.empty:
                continue
                
            # Sort by date
            if "date" not in df.columns:
                 df = df.reset_index() # just in case
            df = df.sort_values("date").reset_index(drop=True)
            
            if len(df) == 0:
                continue

            last_row = df.iloc[-1]
            
            # 3. Validation: Ensure we have the EMA columns
            # build_features calculates 'ema_20', 'ema_50', 'ema_200' if configured in features.yml
            # If missing, treat as NaNs
            
            ema20 = last_row.get("ema_20", np.nan)
            ema50 = last_row.get("ema_50", np.nan)
            ema200 = last_row.get("ema_200", np.nan)
            
            # Prefer adj_close if avail, else close
            price = last_row.get("adj_close", last_row.get("close", np.nan))
            if pd.isna(price) and "close" in last_row:
                 price = last_row["close"]
            
            # 4. Calculate Logic
            
            # Flag: is_200_ema_up
            # Logic: EMA_200(now) > EMA_200(t-20)
            is_200_up = False
            if len(df) >= 21:
                ema_200_now = ema200
                # t-20 means row index -21 (since -1 is now)
                ema_200_prev = df.iloc[-21].get("ema_200", np.nan)
                
                if pd.notna(ema_200_now) and pd.notna(ema_200_prev):
                    is_200_up = bool(ema_200_now > ema_200_prev)
            
            # Flag: is_ema_stacked_up
            # Logic: EMA_20 > EMA_50 > EMA_200
            is_stacked_up = False
            if pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200):
                is_stacked_up = bool((ema20 > ema50) and (ema50 > ema200))

            # Flag: is_price_above_stack
            # Logic: Price > All 3 EMAs
            is_price_above = False
            if pd.notna(price) and pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200):
                is_price_above = bool((price > ema20) and (price > ema50) and (price > ema200))
            
            # Calculate EMA Age (Consecutive Days in Current State)
            ema_age = 0
            if len(df) > 0:
                # Iterate backwards from the last row
                # We want to count how long the 'is_stacked_up' condition has matched the current 'is_stacked_up' status
                for i in range(len(df) - 1, -1, -1):
                    row = df.iloc[i]
                    e20 = row.get("ema_20", np.nan)
                    e50 = row.get("ema_50", np.nan)
                    e200 = row.get("ema_200", np.nan)
                    
                    if pd.isna(e20) or pd.isna(e50) or pd.isna(e200):
                        break
                        
                    daily_stacked = bool((e20 > e50) and (e50 > e200))
                    
                    if daily_stacked == is_stacked_up:
                        ema_age += 1
                    else:
                        break
            
            results.append({
                "date": last_row["date"],
                "ticker": ticker,
                "close": float(price) if pd.notna(price) else None,
                "ema_20": float(ema20) if pd.notna(ema20) else None,
                "ema_50": float(ema50) if pd.notna(ema50) else None,
                "ema_200": float(ema200) if pd.notna(ema200) else None,
                "is_ema_stacked_up": is_stacked_up,
                "is_price_above_stack": is_price_above,
                "is_200_ema_up": is_200_up,
                "ema_age": ema_age
            })
            
        except Exception as e:
            LOG.error(f"Error processing {ticker} for SMA Stack: {e}")

    # 5. Save Aggregate
    if results:
        df_out = pd.DataFrame(results)
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ANALYTICS_DIR / "sma_stack_daily.parquet"
        df_out.to_parquet(out_path)
        LOG.info(f"Saved daily SMA Stack to {out_path} ({len(df_out)} tickers)")
    else:
        LOG.warning("No results generated for SMA Stack.")

if __name__ == "__main__":
    calculate_and_save_sma_stack()
