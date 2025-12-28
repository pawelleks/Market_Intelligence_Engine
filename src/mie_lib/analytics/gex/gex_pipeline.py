"""
Parallel GEX (Gamma Exposure) Pipeline.

Uses Massive flat file (OPTIONS) + yfinance (SPOT) for GEX calculation.
Implements ThreadPoolExecutor for parallel spot price fetching.

Data Hierarchy:
- OPTIONS: Massive Flat Files (source of truth)
- SPOT: yfinance via ThreadPoolExecutor
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

LOG = logging.getLogger(__name__)


@dataclass
class SpotPriceResult:
    """Result of fetching spot price from yfinance."""
    ticker: str
    spot: Optional[float]
    source: str
    error: Optional[str] = None


def _fetch_spot_price(ticker: str) -> SpotPriceResult:
    """
    PURE FETCH: Get current/latest spot price from yfinance.
    Thread-safe: no shared state mutation.
    """
    try:
        import yfinance as yf
        
        t = yf.Ticker(ticker)
        
        # Try fast_info first
        try:
            spot = t.fast_info.get('last_price') or t.fast_info.get('regularMarketPrice')
            if spot:
                return SpotPriceResult(ticker=ticker, spot=float(spot), source="yfinance_fast")
        except:
            pass
        
        # Fallback to history
        hist = t.history(period="2d")
        if not hist.empty:
            spot = float(hist["Close"].iloc[-1])
            return SpotPriceResult(ticker=ticker, spot=spot, source="yfinance")
        
        return SpotPriceResult(ticker=ticker, spot=None, source="no_data")
        
    except Exception as e:
        LOG.warning(f"Failed to fetch spot for {ticker}: {e}")
        return SpotPriceResult(ticker=ticker, spot=None, source="error", error=str(e))


def _process_gex_for_ticker(
    ticker: str,
    df_ticker: pd.DataFrame,
    spot: float,
    target_date: date,
    engine: Any
) -> Dict[str, Any]:
    """
    Calculate GEX for a single ticker.
    
    Args:
        ticker: Underlying ticker
        df_ticker: Options data for this ticker from Massive
        spot: Spot price
        target_date: As-of date
        engine: GEXEngine instance
        
    Returns:
        Dict with GEX metrics or error
    """
    if df_ticker.empty:
        return {"error": "no_options_data"}
    
    if spot is None:
        return {"error": "no_spot_price"}
    
    try:
        # Ensure required columns
        if 'type' in df_ticker.columns and 'option_type' not in df_ticker.columns:
            df_ticker = df_ticker.copy()
            df_ticker['option_type'] = df_ticker['type'].apply(
                lambda x: 'C' if str(x).strip().lower() == 'call' else 'P'
            )
        
        # Ensure oi/iv columns exist
        if 'oi' not in df_ticker.columns:
            df_ticker['oi'] = df_ticker.get('open_interest', 0)
        if 'iv' not in df_ticker.columns:
            df_ticker['iv'] = df_ticker.get('implied_volatility', np.nan)
        
        # Calculate GEX
        result = engine.calculate_gex_from_frame(ticker, df_ticker, spot, as_of=target_date)
        
        if result:
            return {"status": "ok", "data": result}
        else:
            return {"error": "calculation_failed"}
            
    except Exception as e:
        LOG.error(f"GEX calculation failed for {ticker}: {e}")
        return {"error": str(e)}


def run_gex_pipeline_parallel(
    tickers: List[str],
    target_date: str = None,
    max_workers: int = 10,
    online_mode: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for parallel GEX pipeline.
    
    Architecture:
    1. Load Massive flat file ONCE (already downloaded)
    2. Fetch spot prices in PARALLEL (yfinance via ThreadPoolExecutor)
    3. Calculate GEX for each ticker (CPU-bound, sequential but fast)
    4. Save results
    
    Args:
        tickers: List of underlying tickers to process
        target_date: YYYY-MM-DD (defaults to today)
        max_workers: Number of parallel threads for spot fetch
        online_mode: If True, fetch options from yfinance (fallback)
        
    Returns:
        Dict with processing results and statistics
    """
    from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
    from mie_lib.analytics.gex.gex_engine import GEXEngine
    
    if target_date is None:
        target_date = str(date.today())
    
    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    
    LOG.info(f"Starting GEX Pipeline: {len(tickers)} tickers, date={target_date}, workers={max_workers}")
    
    # ========== STEP 1: Load Massive Data (Single Read) ==========
    
    loader = MassiveOptionsLoader()
    engine = GEXEngine()
    
    all_options = pd.DataFrame()
    if not online_mode:
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
    if not all_options.empty and "underlying_ticker" in all_options.columns:
        for ticker in tickers:
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
            except Exception as e:
                spot_errors.append(ticker)
                LOG.error(f"Spot fetch exception for {ticker}: {e}")
    
    LOG.info(f"Spot prices: {len(spot_prices)} success, {len(spot_errors)} errors")
    
    # ========== STEP 3: Calculate GEX (Sequential, Fast) ==========
    
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
        
        if spot is None:
            results["failed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "error",
                "error": "no_spot_price"
            })
            continue
        
        if options.empty and not online_mode:
            results["skipped"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "skipped",
                "error": "no_options_data"
            })
            continue
        
        # Calculate GEX
        if online_mode:
            # Online mode: fetch from API
            try:
                gex_data = engine.fetch_and_calculate_gex(ticker)
                if gex_data:
                    results["success"] += 1
                    results["details"].append({"ticker": ticker, "status": "ok"})
                else:
                    results["failed"] += 1
                    results["details"].append({"ticker": ticker, "status": "error", "error": "online_fetch_failed"})
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"ticker": ticker, "status": "error", "error": str(e)})
        else:
            # Offline mode: use Massive data
            gex_result = _process_gex_for_ticker(ticker, options, spot, target_date_obj, engine)
            
            if gex_result.get("status") == "ok":
                results["success"] += 1
                results["details"].append({"ticker": ticker, "status": "ok"})
            else:
                results["failed"] += 1
                results["details"].append({
                    "ticker": ticker,
                    "status": "error",
                    "error": gex_result.get("error", "unknown")
                })
        
        results["processed"] += 1
    
    LOG.info(f"GEX Pipeline complete: success={results['success']}, failed={results['failed']}, skipped={results['skipped']}")
    
    return results
