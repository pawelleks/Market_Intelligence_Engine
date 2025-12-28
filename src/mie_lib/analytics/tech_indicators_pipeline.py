"""
Parallel Technical Indicators Pipeline.

Parallelizes the calculation of technical indicators (SMA Stack, ADX, PSAR, Ichimoku)
using ThreadPoolExecutor with one thread per ticker.

CPU-bound but dominated by disk I/O for reading parquet files, so threading helps.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Callable
import pandas as pd
import numpy as np

from mie_lib.utils.logging import get_logger
from mie_lib.utils.config import load_named_config
from mie_lib.utils.paths import DATA_DIR

LOG = get_logger("tech_indicators_pipeline")
ANALYTICS_DIR = DATA_DIR / "analytics"


def _process_sma_stack_for_ticker(ticker: str) -> Dict[str, Any]:
    """
    Calculate SMA Stack metrics for a single ticker.
    Thread-safe: only reads and returns data, no global state mutation.
    """
    from mie_lib.features.build_features import build_features_for_ticker
    
    try:
        # Build/Get Features
        res = build_features_for_ticker(ticker, mode='update', lookback=30)
        parquet_path = res.get("parquet")
        
        if not parquet_path or not Path(parquet_path).exists():
            return {"ticker": ticker, "error": "feature_file_missing"}
        
        df = pd.read_parquet(parquet_path)
        
        if df.empty:
            return {"ticker": ticker, "error": "empty_dataframe"}
        
        # Sort by date
        if "date" not in df.columns:
            df = df.reset_index()
        df = df.sort_values("date").reset_index(drop=True)
        
        if len(df) == 0:
            return {"ticker": ticker, "error": "no_rows"}
        
        last_row = df.iloc[-1]
        
        # Get EMA values
        ema20 = last_row.get("ema_20", np.nan)
        ema50 = last_row.get("ema_50", np.nan)
        ema200 = last_row.get("ema_200", np.nan)
        
        # Get price
        price = last_row.get("adj_close", last_row.get("close", np.nan))
        if pd.isna(price) and "close" in last_row:
            price = last_row["close"]
        
        # Calculate is_200_up
        is_200_up = False
        if len(df) >= 21:
            ema_200_now = ema200
            ema_200_prev = df.iloc[-21].get("ema_200", np.nan)
            if pd.notna(ema_200_now) and pd.notna(ema_200_prev):
                is_200_up = bool(ema_200_now > ema_200_prev)
        
        # Calculate is_stacked_up
        is_stacked_up = False
        if pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200):
            is_stacked_up = bool((ema20 > ema50) and (ema50 > ema200))
        
        # Calculate is_price_above
        is_price_above = False
        if pd.notna(price) and pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200):
            is_price_above = bool((price > ema20) and (price > ema50) and (price > ema200))
        
        # Calculate EMA Age
        ema_age = 0
        if len(df) > 0:
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
        
        return {
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
        }
        
    except Exception as e:
        LOG.error(f"Error processing {ticker} for SMA Stack: {e}")
        return {"ticker": ticker, "error": str(e)}


def run_sma_stack_parallel(tickers: List[str] = None, max_workers: int = 10) -> Dict[str, Any]:
    """
    Parallel SMA Stack calculation.
    
    Args:
        tickers: List of tickers (defaults to config)
        max_workers: Thread pool size
        
    Returns:
        Dict with results and statistics
    """
    # Load tickers from config if not provided
    if tickers is None:
        try:
            tcfg = load_named_config("ticker_list")
            tickers = tcfg.get("tickers", []) if isinstance(tcfg, dict) else []
        except Exception as e:
            LOG.error(f"Failed to load ticker list: {e}")
            return {"error": "no_tickers", "processed": 0}
    
    if not tickers:
        LOG.warning("No tickers found")
        return {"error": "empty_tickers", "processed": 0}
    
    LOG.info(f"Starting parallel SMA Stack calculation: {len(tickers)} tickers, {max_workers} workers")
    
    results = []
    errors = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(_process_sma_stack_for_ticker, ticker): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result(timeout=60)
                if "error" in result:
                    errors.append(result)
                else:
                    results.append(result)
            except Exception as e:
                LOG.error(f"Exception processing {ticker}: {e}")
                errors.append({"ticker": ticker, "error": str(e)})
    
    # Save results
    if results:
        df_out = pd.DataFrame(results)
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ANALYTICS_DIR / "sma_stack_daily.parquet"
        df_out.to_parquet(out_path)
        LOG.info(f"Saved SMA Stack to {out_path} ({len(df_out)} tickers)")
    
    LOG.info(f"SMA Stack complete: success={len(results)}, failed={len(errors)}")
    
    return {
        "processed": len(results) + len(errors),
        "success": len(results),
        "failed": len(errors),
        "errors": errors[:5]  # First 5 errors for debugging
    }


def run_technical_indicators_parallel(
    indicators: List[str] = None,
    max_workers: int = 10
) -> Dict[str, Dict[str, Any]]:
    """
    Run multiple technical indicator calculations in parallel.
    
    Args:
        indicators: List of indicator names to run (defaults to all)
        max_workers: Thread pool size for each indicator
        
    Returns:
        Dict mapping indicator name to results
    """
    if indicators is None:
        indicators = ["sma_stack"]  # Add more as we implement them
    
    results = {}
    
    if "sma_stack" in indicators:
        LOG.info("Running parallel SMA Stack...")
        results["sma_stack"] = run_sma_stack_parallel(max_workers=max_workers)
    
    return results
