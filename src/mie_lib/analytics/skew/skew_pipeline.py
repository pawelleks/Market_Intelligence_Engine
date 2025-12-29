"""
Parallel Skew/PCR Pipeline.

Uses Massive flat file (OPTIONS) + yfinance (SPOT) to calculate sentiment metrics.
Implements streaming pattern with ThreadPoolExecutor for memory-safe parallel processing.

Data Hierarchy:
- OPTIONS: Massive Flat Files (source of truth)
- SPOT: yfinance (for underlying prices only)
"""

"""
⛔ CRITICAL ARCHITECTURE CONSTRAINT (READ BEFORE MODIFYING):
-----------------------------------------------------------
This module adheres to the strict "Split-Source" Data Strategy defined in agent_rules.md

OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.
EXCEPTION: If Massive data is missing Greeks (IV, OI) or empty, yfinance Fallback is PERMITTED to ensure functionality.

ENRICHMENT: yfinance is allowed for underlying price/metadata and Greeks fallback.

Any attempt to replace the flat-file ingest with an API call (outside the fallback scenario) is a violation of project constraints.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


def _fetch_spot_price(ticker: str, target_date: Optional[str] = None) -> SpotPriceResult:
    """
    PURE FETCH: Get spot price from yfinance.
    If target_date is provided, fetches historical close for that date.
    Otherwise fetches current/latest price.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        
        today_str = date.today().isoformat()
        
        # Scenario A: Specific Historical Date
        if target_date and target_date != today_str:
            try:
                # Need a small buffer to ensure we get exactly that day
                d_obj = datetime.strptime(target_date, "%Y-%m-%d")
                end_date = (d_obj + timedelta(days=1)).strftime("%Y-%m-%d")
                
                # Fetch 1-day history
                hist = t.history(start=target_date, end=end_date)
                if not hist.empty:
                    spot = float(hist["Close"].iloc[0])
                    return SpotPriceResult(ticker=ticker, spot=spot, source=f"yfinance_hist_{target_date}")
            except Exception as e:
                LOG.debug(f"Historical spot failed for {ticker} on {target_date}: {e}")
        
        # Scenario B: Current/Latest Price
        try:
            # Try fast info first (no network call for historical)
            spot = t.fast_info['last_price']
            if spot and spot > 0:
                return SpotPriceResult(ticker=ticker, spot=float(spot), source="yfinance_fast")
        except:
            pass
            
        hist = t.history(period="2d")  # 2 days to handle weekends
        if hist.empty:
            return SpotPriceResult(ticker=ticker, spot=None, source="no_data")
        
        spot = float(hist["Close"].iloc[-1])
        return SpotPriceResult(ticker=ticker, spot=spot, source="yfinance_hist_latest")
        
    except Exception as e:
        LOG.warning(f"Failed to fetch spot for {ticker}: {e}")
        return SpotPriceResult(ticker=ticker, spot=None, source="error", error=str(e))


def _fetch_yfinance_chain_hybrid(ticker: str, target_dte_min: int = 15, target_dte_max: int = 60) -> pd.DataFrame:
    """
    Fallback: Fetches option chain from yfinance if Massive is missing data.
    Optimized to fetch only expirations within target DTE range (default 15-60 days).
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return pd.DataFrame()
            
        today = date.today()
        valid_exps = []
        
        # Filter expirations
        for e in exps:
            try:
                edate = datetime.strptime(e, "%Y-%m-%d").date()
                days = (edate - today).days
                if target_dte_min <= days <= target_dte_max:
                    valid_exps.append(e)
            except:
                continue
                
        if not valid_exps:
            # Fallback to first available if none in range? 
            # Or assume Skew is irrelevant if no monthlys?
            # Let's try to get at least one if possible, maybe closest to 30?
            if exps:
                # Find closest to 30
                valid_exps = [min(exps, key=lambda x: abs((datetime.strptime(x, "%Y-%m-%d").date() - today).days - 30))]
            else:
                return pd.DataFrame()

        dfs = []
        for e in valid_exps:
            try:
                chain = t.option_chain(e)
                c, p = chain.calls, chain.puts
                c['type'] = 'call'
                p['type'] = 'put'
                c['expiration'] = e
                p['expiration'] = e
                dfs.extend([c, p])
            except:
                continue
                
        if not dfs:
            return pd.DataFrame()
            
        df = pd.concat(dfs, ignore_index=True)
        
        # Normalize columns matched to skew logic
        # logic expects: strike, type, iv (or impliedVolatility), oi (or openInterest), volume
        df = df.rename(columns={
            'impliedVolatility': 'iv',
            'openInterest': 'oi',
            'lastPrice': 'close' # approximate
        })
        
        return df

    except Exception as e:
        LOG.error(f"Hybrid fetch failed for {ticker}: {e}")
        return pd.DataFrame()


def _calculate_skew_for_ticker(
    ticker: str,
    spot: float,
    options_df: pd.DataFrame,
    target_date: str
) -> Dict[str, Any]:
    """
    Calculate Skew and PCR metrics for a single ticker.
    Arg: options_df can be empty or deficient (missing Greeks).
    """
    source_used = "massive"
    
    # 1. Calculate Historical PCR (Prioritize actual daily volume/OI from Massive)
    hist_pcr_volume = None
    hist_pcr_oi = None
    
    if not options_df.empty and "type" in options_df.columns:
        c_hist = options_df[options_df["type"].str.lower() == "call"]
        p_hist = options_df[options_df["type"].str.lower() == "put"]
        
        if not c_hist.empty and not p_hist.empty:
            if "volume" in options_df.columns:
                cv, pv = c_hist["volume"].sum(), p_hist["volume"].sum()
                if cv > 0: hist_pcr_volume = float(pv / cv)
            oi_col = "oi" if "oi" in options_df.columns else ("open_interest" if "open_interest" in options_df.columns else None)
            if oi_col:
                co, po = c_hist[oi_col].sum(), p_hist[oi_col].sum()
                if co > 0: hist_pcr_oi = float(po / co)

    # 2. Validate Data Quality (Do we have Greeks for Skew?)
    has_greeks = False
    if not options_df.empty:
        has_iv = 'iv' in options_df.columns or 'implied_volatility' in options_df.columns
        if has_iv:
            iv_col = 'iv' if 'iv' in options_df.columns else 'implied_volatility'
            if options_df[iv_col].sum() > 0:
                has_greeks = True
    
    # 3. Hybrid Fallback for Greeks (Skew)
    hybrid_df = pd.DataFrame()
    if not has_greeks:
        LOG.info(f"Massive data missing Greeks for {ticker}. Attempting yfinance fallback for Skew (Date: {target_date})...")
        hybrid_df = _fetch_yfinance_chain_hybrid(ticker)
        if hybrid_df.empty and options_df.empty:
            return {"error": "no_options_data_total_failure"}
        source_used = "hybrid_yfinance" if not hybrid_df.empty else "massive_partial"

    # 4. Proceed with Calculations
    pcr_volume = hist_pcr_volume
    pcr_oi = hist_pcr_oi
    
    # If massive PCR failed (empty file etc) but we have hybrid data, use hybrid PCR as fallback
    if (pcr_volume is None) and not hybrid_df.empty:
        c_hyb = hybrid_df[hybrid_df["type"].str.lower() == "call"]
        p_hyb = hybrid_df[hybrid_df["type"].str.lower() == "put"]
        if not c_hyb.empty and not p_hyb.empty:
            cv, pv = c_hyb["volume"].sum(), p_hyb["volume"].sum()
            if cv > 0: pcr_volume = float(pv / cv)
            co, po = c_hyb["oi"].sum(), p_hyb["oi"].sum()
            if co > 0: pcr_oi = float(po / co)

    # Use the best dataset for Skew
    calc_df = options_df if (has_greeks or hybrid_df.empty) else hybrid_df
    if "type" not in calc_df.columns:
        return {"error": "missing_type_column"}
    
    calls = calc_df[calc_df["type"].str.lower() == "call"].copy()
    puts = calc_df[calc_df["type"].str.lower() == "put"].copy()
    
    if calls.empty or puts.empty:
        return {"error": "missing_call_or_put"}
    
    # ========== Skew Calculation ==========
    
    skew_25d = None
    iv_col = "iv" if ("iv" in calc_df.columns and calc_df["iv"].notna().any()) else (
        "implied_volatility" if "implied_volatility" in calc_df.columns else None
    )
    
    if "strike" in calc_df.columns and iv_col:
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
    
    pcr_for_sentiment = pcr_volume if pcr_volume is not None else pcr_oi
    
    sentiment_score = None
    if pcr_for_sentiment is not None or skew_25d is not None:
        pcr_signal = 0
        skew_signal = 0
        
        if pcr_for_sentiment is not None:
            # Shift center to 0.85 approx for options-heavy market
            pcr_signal = (pcr_for_sentiment - 0.9) * 0.5
        
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
        "source": source_used,
        "options_count": len(calc_df)
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
       * Fallback to yfinance for Chains if Massive data sucks.
    4. Write to hybrid storage (by_ticker/, by_date/, latest.json)
    """
    if target_date is None:
        target_date = str(date.today())
    
    LOG.info(f"Starting Skew Pipeline: {len(tickers)} tickers, date={target_date}, workers={max_workers}")
    
    # ========== STEP 1: Load Massive Data (Single Read) ==========
    
    loader = MassiveOptionsLoader()
    
    # Load ONCE for all tickers
    # Note: If file missing, returns Empty DF. Hybrid fallback handled inside.
    all_options = loader.load_day_aggregates(target_date, tickers=tickers)
    
    if all_options.empty:
        LOG.warning(f"No options data from Massive for {target_date}. Will use Full Hybrid Fallback.")
        # Do NOT return error. Proceed with empty map, forcing Hybrid for all.
        pass
    else:
        LOG.info(f"Loaded {len(all_options)} options rows from Massive flat file")
    
    # Pre-group by ticker for O(1) lookup
    options_by_ticker: Dict[str, pd.DataFrame] = {}
    if not all_options.empty and "underlying_ticker" in all_options.columns:
        for ticker in tickers:
            clean_ticker = ticker.upper().lstrip("^")
            ticker_data = all_options[all_options["underlying_ticker"] == clean_ticker].copy()
            if not ticker_data.empty:
                options_by_ticker[ticker] = ticker_data
    
    # ========== STEP 2: Parallel Spot Fetch (yfinance) ==========
    
    spot_prices: Dict[str, float] = {}
    spot_errors: List[str] = []
    
    LOG.info(f"Fetching spot prices with {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(_fetch_spot_price, ticker, target_date): ticker
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
    
    # ========== STEP 3: Calculate Metrics (Sequential + fallback fetching) ==========
    
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
        
        # Skip if no spot price (we need spot for Skew calc)
        if spot is None:
            results["failed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "error",
                "error": "no_spot_price"
            })
            continue
        
        # Calculate metrics (Handles Hybrid Fetch internally if options empty/bad)
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
                "pcr": metrics.get("pcr_volume"),
                "source": metrics.get("source")
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
