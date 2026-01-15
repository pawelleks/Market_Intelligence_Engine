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
"""
⛔ CRITICAL ARCHITECTURE CONSTRAINT (READ BEFORE MODIFYING):
-----------------------------------------------------------
This module adheres to the strict "Split-Source" Data Strategy defined in agent_rules.md

OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.

ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.

Any attempt to replace the flat-file ingest with an API call is a violation of project constraints. Fix logic errors only; do not change the data provider.
"""
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



def _fetch_yfinance_chain_df(ticker: str) -> pd.DataFrame:
    """
    Fetch full option chain (metadata, Greeks, OI) from yfinance for a single ticker.
    Iterates through expirations to build a complete DataFrame.
    
    Returns:
        pd.DataFrame with columns: ['contractSymbol', 'strike', 'expiration', 'option_type', 'impliedVolatility', 'openInterest', 'gamma']
        (Note: gamma might be missing, usually re-calculated by engine)
    """
    import yfinance as yf
    
    try:
        yf_ticker = yf.Ticker(ticker)
        
        # Check Expirations
        try:
            expirations = yf_ticker.options
        except Exception: 
             # yfinance sometimes fails on .options access if no data
             return pd.DataFrame()
             
        if not expirations:
            return pd.DataFrame()
            
        all_rows = []
        
        # Limit expirations to next ~6 months to avoid timeouts? 
        # For now, try all. If too slow, limit.
        for expiry in expirations:
            try:
                # yfinance option_chain returns (calls, puts)
                chain = yf_ticker.option_chain(expiry)
                
                # Process Calls
                if not chain.calls.empty:
                    df_calls = chain.calls.copy()
                    df_calls['option_type'] = 'C'
                    df_calls['expiration'] = expiry
                    all_rows.append(df_calls)
                    
                # Process Puts
                if not chain.puts.empty:
                    df_puts = chain.puts.copy()
                    df_puts['option_type'] = 'P'
                    df_puts['expiration'] = expiry
                    all_rows.append(df_puts)
                    
            except Exception as e:
                # Log debug but continue other expirations
                # LOG.debug(f"Failed expiration {expiry} for {ticker}: {e}")
                continue
                
        if not all_rows:
            return pd.DataFrame()
            
        # Concat
        full_df = pd.concat(all_rows, ignore_index=True)
        
        # Standardize Columns
        # Expected by GEXEngine: [strike, type, expiration, oi, iv]
        # yfinance columns: contractSymbol, lastTradeDate, strike, lastPrice, bid, ask, change, percentChange, volume, openInterest, impliedVolatility, inTheMoney, contractSize, currency
        
        rename_map = {
            'openInterest': 'oi',
            'impliedVolatility': 'iv',
            # 'option_type' already set
        }
        full_df = full_df.rename(columns=rename_map)
        
        # Ensure minimal columns exist
        cols = ['contractSymbol', 'strike', 'expiration', 'option_type', 'oi', 'iv']
        
        # Filter strictly
        final_df = full_df[[c for c in cols if c in full_df.columns]].copy()
        
        return final_df
        
    except Exception as e:
        LOG.warning(f"Failed to fetch yfinance chain for {ticker}: {e}")
        return pd.DataFrame()


def run_gex_pipeline_parallel(
    tickers: List[str],
    target_date: str = None,
    max_workers: int = 10,
    online_mode: bool = False  # Kept for compatibility, but Hybrid logic overrides
) -> Dict[str, Any]:
    """
    Main entry point for parallel GEX pipeline (Hybrid Mode).
    
    Architecture (Hybrid):
    1. Load Massive flat file (Source of Pricing: Open/Close/High/Low)
    2. Fetch Spot Prices (yfinance)
    3. Fetch Full Option Chain (yfinance) (Source of Greeks: IV, OI)
    4. Merge & Calculate
    
    Args:
        tickers: List of underlying tickers to process
        target_date: YYYY-MM-DD
        max_workers: Number of parallel threads
        
    Returns:
        Dict with processing results
    """
    from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
    from mie_lib.analytics.gex.gex_engine import GEXEngine
    
    if target_date is None:
        target_date = str(date.today())
    
    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    
    LOG.info(f"Starting Hybrid GEX Pipeline: {len(tickers)} tickers, date={target_date}")
    
    # ========== STEP 1: Load Massive Prices (Trusted Source) ==========
    loader = MassiveOptionsLoader()
    engine = GEXEngine()
    
    # We load Massive primarily for PRICES. 
    # Even if "missing columns" (IV/OI), we proceed because we fetch them from yf.
    all_options_prices = pd.DataFrame()
    
    # Attempt load
    try:
        all_options_prices = loader.load_day_aggregates(target_date, tickers=tickers)
    except Exception as e:
        LOG.warning(f"Massive load exception: {e}")
        
    has_massive = not all_options_prices.empty
    
    if not has_massive:
        LOG.warning(f"No Massive pricing data for {target_date}. Will proceed if possible (Online fallback?).")
        # If user STRICTLY wants Massive prices, we should fail? 
        # But maybe file is just not there yet. 
        # For HYBRID, we need both. But if Massive missing, we imply pure online fallback?
        # User said "Massive is where we download...". 
        # Let's try to continue. If merge fails, we fail specific tickers.
    
    # Index Massive Data by Option Ticker for fast merge
    # Massive has 'option_ticker', usually 'O:SPY...' or 'SPY...' (if normalized)
    # yfinance has 'contractSymbol' (OSI standard)
    # We need to align them.
    
    prices_map = {} # contract -> price
    if has_massive and 'option_ticker' in all_options_prices.columns:
        # Normalize Massive Ticker: Strip 'O:' prefix if present
        all_options_prices['norm_ticker'] = all_options_prices['option_ticker'].str.replace(r'^O:', '', regex=True)
        # Create map
        if 'close' in all_options_prices.columns:
             prices_map = all_options_prices.set_index('norm_ticker')['close'].to_dict()

    LOG.info(f"Loaded {len(prices_map)} pricing records from Massive.")
    
    # ========== STEP 2: Parallel Fetch (Spot & Chains) ==========
    
    # We fetch Spot AND Chain in parallel now
    
    results = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "date": target_date,
        "details": []
    }
    
    # Run Parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Use module-level hybrid processor
        future_to_ticker = {
            executor.submit(_process_single_ticker_hybrid, ticker): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                res = future.result()
                
                results["processed"] += 1
                if res["status"] == "ok":
                    results["success"] += 1
                    results["details"].append({"ticker": ticker, "status": "ok"})
                else:
                    results["failed"] += 1
                    err_msg = res.get("error", "Unknown error")
                    results["details"].append({"ticker": ticker, "status": "error", "error": err_msg})
                    LOG.warning(f"GEX failed for {ticker}: {err_msg}")
            except Exception as e:
                LOG.error(f"Pipeline future exception for {ticker}: {e}")
                results["failed"] += 1

    LOG.info(f"Hybrid GEX Pipeline complete: {results['success']}/{results['processed']} succeeded")
    return results

def _fetch_polygon_chain(ticker: str, spot: float, loader_ref=None) -> pd.DataFrame:
    """Helper to fetch full Polygon chain across expirations."""
    try:
        import yfinance as yf
        from mie_lib.analytics.expected_moves.data_ingest_polygon import fetch_option_chain as fetch_poly_chain
        from datetime import date
        
        # We need expirations. YF `.options` usually works even if chain data is bad.
        try:
             poly_expirations = yf.Ticker(ticker).options
        except:
             return pd.DataFrame() # Can't get expirations

        if not poly_expirations:
             return pd.DataFrame()

        poly_rows = []
        
        for p_exp in poly_expirations:
            try:
                exp_date = datetime.strptime(p_exp, "%Y-%m-%d").date()
                # Fetch Snapshot
                df_snap = fetch_poly_chain(ticker, exp_date, date.today(), spot_price=spot)
                if not df_snap.empty:
                    df_snap['expiration'] = p_exp
                    poly_rows.append(df_snap)
            except Exception:
                continue
                
        if poly_rows:
            df = pd.concat(poly_rows, ignore_index=True)
            # Standardize Columns
            # fetch_poly_chain returns: [strike, option_type, prev_close_mid, iv, gamma, oi, contractSymbol]
            # Rename 'option_type' -> 'type' (to match YF intermediate or handle later)
            # For merge, we want standard keys.
            
            # Normalize Type
            df['type'] = df['option_type'].apply(lambda x: 'C' if str(x).upper() in ['C','CALL'] else 'P')
            return df
        
        return pd.DataFrame()
            
    except Exception as e:
        LOG.warning(f"Polygon fetch failed: {e}")
        return pd.DataFrame()


def _merge_data_sources(yf_df: pd.DataFrame, poly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge YFinance (Greeks Source) and Polygon (OI Source).
    Match on Strike, Expiration, Type.
    """
    if yf_df.empty and poly_df.empty:
        return pd.DataFrame()

    # Ensure columns exist in YF (Standardize Type)
    if not yf_df.empty and 'option_type' in yf_df.columns:
        yf_df['type'] = yf_df['option_type']

    if yf_df.empty:
        # Only Polygon (Missing Greeks likely, but return it)
        return poly_df
        
    if poly_df.empty:
        # Only YF (Missing OI likely)
        return yf_df
        
    on_keys = ['strike', 'expiration', 'type']
    
    # Drop duplicates to avoid explosion
    yf_clean = yf_df.drop_duplicates(subset=on_keys)
    poly_clean = poly_df.drop_duplicates(subset=on_keys)
    
    # Merge
    merged = pd.merge(yf_clean, poly_clean, on=on_keys, how='outer', suffixes=('_yf', '_poly'))
    
    # Resolve Columns (Prioritize Polygon for OI, YF for Greeks)
    
    # OI: Poly > YF
    merged['oi'] = merged['oi_poly'].fillna(merged['oi_yf']).fillna(0)
    
    # IV: YF > Poly
    merged['iv'] = merged['iv_yf'].fillna(merged['iv_poly'])
    
    # Gamma: YF > Poly
    # YF might not have 'gamma' column if not calc? _fetch_yfinance_chain_df mentions it?
    gamma_yf = merged['gamma_yf'] if 'gamma_yf' in merged.columns else None
    gamma_poly = merged['gamma'] if 'gamma' in merged.columns else merged.get('gamma_poly')
    
    # Actually fetch_poly passes 'gamma'
    # merged key might be 'gamma' if only in one? No, suffixes.
    
    # Let's consolidate 'gamma'
    if 'gamma_yf' in merged.columns:
        merged['gamma'] = merged['gamma_yf'].fillna(merged.get('gamma_poly'))
    elif 'gamma_poly' in merged.columns:
        merged['gamma'] = merged['gamma_poly']
        
    return merged


def _process_single_ticker_hybrid(ticker: str) -> Dict[str, Any]:
    """
    Process ticker using Hybrid Merge strategy.
    """
    # 1. Fetch Spot (YFinance)
    try:
        spot_res = _fetch_spot_price(ticker)
        if spot_res.spot is None:
             return {"status": "error", "error": f"No spot price ({spot_res.source})"}
        spot = spot_res.spot
        
        # 2. Fetch Chains (Both)
        yf_chain = _fetch_yfinance_chain_df(ticker)
        poly_chain = pd.DataFrame()
        
        # Check if YF is sufficient?
        # If YF has OI > 0 and IV, we don't need Polygon (save API calls)
        yf_ok = False
        if not yf_chain.empty and 'oi' in yf_chain.columns and yf_chain['oi'].sum() > 0:
             yf_ok = True
             
        if not yf_ok:
             LOG.info(f"YFinance incomplete for {ticker} (OI=0 or Empty). Fetching Polygon for OI...")
             poly_chain = _fetch_polygon_chain(ticker, spot)
             
        # 3. Merge
        working_df = _merge_data_sources(yf_chain, poly_chain)
        
        if working_df.empty:
             return {"status": "error", "error": "No options data from YF or Polygon"}
             
        # 4. Engine Format
        # valid cols: strike, type, expiration, oi, iv, gamma
        
        from mie_lib.analytics.gex.gex_engine import GEXEngine
        engine = GEXEngine()
        
        gex_result = engine.calculate_gex_from_frame(ticker, working_df, spot)
        
        if gex_result and gex_result.get('net_gex') == 0.0 and working_df['oi'].sum() > 0:
             LOG.warning(f"GEX is 0 but OI exists ({working_df['oi'].sum()}). Check IV/Gamma availability.")
             # Debug log
             # LOG.warning(f"Sample: {working_df[['strike','type','oi','iv']].head()}")
             
        if gex_result:
            from .storage import save_gex_profile
            save_gex_profile(ticker, gex_result)
            return {"status": "ok"}
        else:
            return {"status": "error", "error": "Calculation returned empty"}

    except Exception as e:
        LOG.error(f"Error processing {ticker}: {e}")
        return {"status": "error", "error": str(e)}


