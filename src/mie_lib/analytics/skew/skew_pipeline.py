"""
Parallel Skew/PCR Pipeline.

Uses Massive flat file (OPTIONS) + yfinance (SPOT) to calculate sentiment metrics.
Implements streaming pattern with ThreadPoolExecutor for memory-safe parallel processing.

Data Hierarchy:
- OPTIONS: Massive Flat Files (source of truth)
- SPOT: yfinance (for underlying prices only)
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
from mie_lib.analytics.skew.storage import save_skew_metrics

LOG = logging.getLogger(__name__)


@dataclass
class SpotPriceResult:
    """Result of fetching spot price from yfinance."""
    ticker: str
    spot: Optional[float]
    source: str  # "yfinance", "cache", "error"
    error: Optional[str] = None


def _fetch_spot_price(ticker: str) -> SpotPriceResult:
    """
    PURE FETCH: Get current/latest spot price from yfinance.
    Thread-safe: no shared state mutation.
    """
    try:
        import yfinance as yf
        
        # Quick fetch - just today's close
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")  # 2 days to handle weekends
        
        if hist.empty:
            return SpotPriceResult(ticker=ticker, spot=None, source="no_data")
        
        spot = float(hist["Close"].iloc[-1])
        return SpotPriceResult(ticker=ticker, spot=spot, source="yfinance")
        
    except Exception as e:
        LOG.warning(f"Failed to fetch spot for {ticker}: {e}")
        return SpotPriceResult(ticker=ticker, spot=None, source="error", error=str(e))


def _calculate_skew_for_ticker(
    ticker: str,
    spot: float,
    options_df: pd.DataFrame,
    target_date: str
) -> Dict[str, Any]:
    """
    Calculate Skew and PCR metrics for a single ticker.
    
    Args:
        ticker: Underlying ticker
        spot: Current spot price
        options_df: Pre-filtered options data from Massive
        target_date: YYYY-MM-DD
        
    Returns:
        Dict with skew metrics
    """
    if options_df.empty:
        return {"error": "no_options_data"}
    
    # Ensure required columns exist
    if "type" not in options_df.columns:
        return {"error": "missing_type_column"}
    
    calls = options_df[options_df["type"].str.lower() == "call"].copy()
    puts = options_df[options_df["type"].str.lower() == "put"].copy()
    
    if calls.empty or puts.empty:
        return {"error": "missing_call_or_put"}
    
    # ========== PCR Calculation ==========
    # Massive files use 'open_interest', normalize to 'oi'
    
    # Volume-based PCR (if volume column exists)
    pcr_volume = None
    if "volume" in options_df.columns:
        put_volume = puts["volume"].sum()
        call_volume = calls["volume"].sum()
        if call_volume > 0:
            pcr_volume = put_volume / call_volume
    
    # OI-based PCR (handle both column names)
    pcr_oi = None
    oi_col = "oi" if "oi" in options_df.columns else ("open_interest" if "open_interest" in options_df.columns else None)
    if oi_col:
        put_oi = puts[oi_col].sum()
        call_oi = calls[oi_col].sum()
        if call_oi > 0:
            pcr_oi = put_oi / call_oi
    
    # ========== Skew Calculation ==========
    # Massive files use 'implied_volatility', normalize to 'iv'
    
    skew_25d = None
    iv_col = "iv" if ("iv" in options_df.columns and options_df["iv"].notna().any()) else (
        "implied_volatility" if "implied_volatility" in options_df.columns else None
    )
    
    if "strike" in options_df.columns and iv_col:
        # 25-Delta Skew approximation using ~5% OTM options
        otm_pct = 0.05
        
        # OTM Put: strike < spot * 0.95
        otm_puts = puts[puts["strike"] < spot * (1 - otm_pct)]
        # OTM Call: strike > spot * 1.05
        otm_calls = calls[calls["strike"] > spot * (1 + otm_pct)]
        
        if not otm_puts.empty and not otm_calls.empty:
            put_iv = otm_puts[iv_col].mean()
            call_iv = otm_calls[iv_col].mean()
            if pd.notna(put_iv) and pd.notna(call_iv) and put_iv > 0 and call_iv > 0:
                skew_25d = put_iv - call_iv
    
    # ========== Sentiment Score ==========
    # Use pcr_oi if pcr_volume is not available (Massive files have OI, not volume)
    
    pcr_for_sentiment = pcr_volume if pcr_volume is not None else pcr_oi
    
    sentiment_score = None
    if pcr_for_sentiment is not None or skew_25d is not None:
        pcr_signal = 0
        skew_signal = 0
        
        if pcr_for_sentiment is not None:
            # PCR > 1 = bearish signal
            pcr_signal = (pcr_for_sentiment - 1) * 0.5
        
        if skew_25d is not None:
            # Positive skew (higher put IV) = bearish signal
            skew_signal = skew_25d * 10
        
        sentiment_score = -(pcr_signal + skew_signal)
        sentiment_score = max(-1, min(1, sentiment_score))  # Clamp to [-1, 1]
    
    # ========== Regime Classification ==========
    
    regime = "neutral"
    if sentiment_score is not None:
        if sentiment_score < -0.3:
            regime = "fear"
        elif sentiment_score > 0.3:
            regime = "greed"
    
    return {
        "skew_25d": round(skew_25d, 4) if skew_25d is not None else None,
        "pcr_volume": round(pcr_volume, 4) if pcr_volume is not None else None,
        "pcr_oi": round(pcr_oi, 4) if pcr_oi is not None else None,
        "sentiment_score": round(sentiment_score, 4) if sentiment_score is not None else None,
        "regime": regime,
        "spot": round(spot, 2),
        "source": "massive",
        "options_count": len(options_df)
    }


def run_skew_pipeline_parallel(
    tickers: List[str],
    target_date: str = None,
    max_workers: int = 10
) -> Dict[str, Any]:
    """
    Main entry point for parallel Skew/PCR pipeline.
    
    Architecture:
    1. Load Massive flat file ONCE (already downloaded by orchestrator)
    2. Fetch spot prices in PARALLEL (yfinance via ThreadPoolExecutor)
    3. Calculate metrics for each ticker (CPU-bound, fast)
    4. Write to hybrid storage (by_ticker/, by_date/, latest.json)
    
    Args:
        tickers: List of underlying tickers to process
        target_date: YYYY-MM-DD (defaults to today)
        max_workers: Number of parallel threads for spot fetch
        
    Returns:
        Dict with processing results and statistics
    """
    if target_date is None:
        target_date = str(date.today())
    
    LOG.info(f"Starting Skew Pipeline: {len(tickers)} tickers, date={target_date}, workers={max_workers}")
    
    # ========== STEP 1: Load Massive Data (Single Read) ==========
    
    loader = MassiveOptionsLoader()
    
    # Load ONCE for all tickers
    all_options = loader.load_day_aggregates(target_date, tickers=tickers)
    
    if all_options.empty:
        LOG.warning(f"No options data from Massive for {target_date}")
        return {
            "error": "no_massive_data",
            "processed": 0,
            "success": 0,
            "failed": len(tickers),
            "date": target_date
        }
    
    LOG.info(f"Loaded {len(all_options)} options rows from Massive flat file")
    
    # Pre-group by ticker for O(1) lookup
    options_by_ticker: Dict[str, pd.DataFrame] = {}
    if "underlying_ticker" in all_options.columns:
        for ticker in tickers:
            # Handle ^ stripping (e.g., ^SPX -> SPX in Massive data)
            clean_ticker = ticker.upper().lstrip("^")
            ticker_data = all_options[all_options["underlying_ticker"] == clean_ticker].copy()
            if not ticker_data.empty:
                options_by_ticker[ticker] = ticker_data
    
    LOG.info(f"Options data available for {len(options_by_ticker)} tickers")
    
    # ========== STEP 2: Parallel Spot Fetch (yfinance) ==========
    
    spot_prices: Dict[str, float] = {}
    spot_errors: List[str] = []
    
    LOG.info(f"Fetching spot prices with {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(_fetch_spot_price, ticker): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result: SpotPriceResult = future.result(timeout=30)
                if result.spot is not None:
                    spot_prices[ticker] = result.spot
                else:
                    spot_errors.append(ticker)
                    LOG.debug(f"No spot price for {ticker}: {result.source}")
            except Exception as e:
                spot_errors.append(ticker)
                LOG.error(f"Spot fetch exception for {ticker}: {e}")
    
    LOG.info(f"Spot prices: {len(spot_prices)} success, {len(spot_errors)} errors")
    
    # ========== STEP 3: Calculate Metrics (Sequential, Fast) ==========
    
    results = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "date": target_date,
        "details": []
    }
    
    for ticker in tickers:
        spot = spot_prices.get(ticker)
        options = options_by_ticker.get(ticker, pd.DataFrame())
        
        # Skip if no spot price
        if spot is None:
            results["failed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "error",
                "error": "no_spot_price"
            })
            continue
        
        # Skip if no options data
        if options.empty:
            results["skipped"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "skipped",
                "error": "no_options_data"
            })
            continue
        
        # Calculate metrics
        metrics = _calculate_skew_for_ticker(ticker, spot, options, target_date)
        
        if "error" in metrics:
            results["failed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "error",
                "error": metrics["error"]
            })
            continue
        
        # Save to Hybrid Storage
        try:
            save_skew_metrics(ticker, target_date, metrics)
            results["success"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "ok",
                "regime": metrics.get("regime"),
                "pcr": metrics.get("pcr_volume")
            })
        except Exception as e:
            LOG.error(f"Failed to save metrics for {ticker}: {e}")
            results["failed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "error",
                "error": f"save_failed: {e}"
            })
        
        results["processed"] += 1
    
    LOG.info(f"Skew Pipeline complete: success={results['success']}, failed={results['failed']}, skipped={results['skipped']}")
    
    return results
