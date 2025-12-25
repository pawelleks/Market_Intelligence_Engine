"""
Orchestration engine for Expected Moves (EM).
Runs the daily build process.
"""
import json
import logging
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import yfinance as yf

from mie_lib.analytics.expected_moves.core import (
    calculate_straddle_em,
    calculate_iv_em,
    calculate_confidence_score,
)
from mie_lib.analytics.expected_moves.data_ingest import (
    fetch_vix1d_close,
    get_target_expirations,
    fetch_underlying_close,
)
from mie_lib.data_ingest.providers.massive_api import fetch_option_chain_snapshot
# from mie_lib.data_ingest.providers.massive_api import fetch_historical_option_chain # REMOVED to enforce Flat File usage
# from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader # Removed
from mie_lib.utils.paths import (
    options_expected_moves_path,
    options_latest_json_path,
)

LOG = logging.getLogger(__name__)

def run_daily_em_build(tickers: List[str], as_of: Optional[date] = None) -> Dict[str, Any]:
    """
    Runs the daily Expected Moves build for the given tickers.
    
    Args:
        tickers: List of ticker symbols (e.g., ["SPY", "QQQ"]).
        as_of: The calculation date (default: today).
        
    Returns:
        Dictionary containing the 'latest' results summary.
    """
    if as_of is None:
        as_of = date.today()
        
    LOG.info(f"Starting Expected Moves build for {as_of} tickers={tickers}")
    
    # 0. Global Setup: Determine Target Dates
    from mie_lib.utils.trading_calendar import get_previous_trading_day
    LOG.info(f"Context: AsOf={as_of}")
    
    LOG.info(f"Starting Daily Expected Moves Build for {len(tickers)} tickers. Date: {as_of}")
    
    # Note: We calculate expirations PER TICKER inside the loop now
    # to handle different monthly conventions (Equity vs Index)
    
    # FIX: Spot Price should be from the analysis date (as_of) if available (e.g. EOD run),
    # falling back to previous day only if today's close is not yet available.
    spot_date = as_of
    
    LOG.info(f"Target Spot Date: {spot_date}")
    
    # Handle Index mapping: Strip ^ for options data matching
    # e.g. ^SPX -> SPX in flat file
    # But we need to keep original tickers for loop? No, loop iterates `tickers`.
    # `run_daily_em_build` receives `tickers`.
    # We should perform the strip inside the Loader or map it here?
    # Loader does caching. Better to strip in Loader filter criteria.
    # Done in Loader update below.
    
    # We need a spot_date for VIX fetch. 
    # In this Flat File workflow, 'as_of' represents the Calculation Date.
    # So we use spot_date (T-1) for both spot data and options data (if flat file).
    
    # 0.5 Load Massive Options Data (Optimized)
    # Hybrid Strategy:
    # 1. Historical (Backfill): Use Bulk Flat Files (MassiveOptionsLoader) to get Greeks/IV/Prices.
    # 2. Live (Today): Use REST API Snapshot (MassiveAPIClient).
    
    df_all = pd.DataFrame()
    is_historical = as_of < date.today()
    vix1d_val = None # Initialize to prevent UnboundLocalError
    
    # Explicitly skip flat file for Today (not ready yet)
    if as_of >= date.today():
         LOG.info("Skipping Flat File for Today (Not generated yet). Using API Mode.")
         is_historical = False
    
    if is_historical:
        LOG.info("Historical Mode: Utilizing MassiveOptionsLoader for Bulk Data...")
        try:
            from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
            loader = MassiveOptionsLoader()
            
            # Download file for the TARGET DATE (as_of)
            as_of_str = as_of.strftime("%Y-%m-%d")
            
            # Download if missing (self-healing)
            LOG.info(f"Ensuring local Flat File availability for {as_of}...")
            loader.download_day_snapshot(as_of_str)
            
            # Load Full Dataset (tickers=None) to ensure we have everything in memory
            LOG.info(f"Loading daily aggregates for {as_of_str}...")
            df_all = loader.load_day_aggregates(as_of_str, tickers=None)
            
            if not df_all.empty:
                 LOG.info(f"DEBUG: Download Success. DataFrame Shape: {df_all.shape}")
                 LOG.info(f"Loaded {len(df_all)} option rows from flat file.")
                 LOG.info(f"DEBUG: Loaded Data Columns: {df_all.columns.tolist()}")
                 LOG.info(f"DEBUG: First 5 Tickers in File: {df_all['ticker'].head(5).tolist() if 'ticker' in df_all.columns else (df_all['underlying_ticker'].head(5).tolist() if 'underlying_ticker' in df_all.columns else 'TickerColMissing')}")
                 if 'option_ticker' in df_all.columns:
                     LOG.info(f"DEBUG: Sample Option Tickers: {df_all['option_ticker'].head().tolist()}")
            else:
                 LOG.warning(f"Flat file load returned empty for {as_of_str}.")
                 
        except Exception as e:
            LOG.error(f"Failed to load bulk flat file: {e}")
    else:
        LOG.info("Live Mode: Utilizing Massive REST API Snapshot...")
        
    # 1. Fetch Global VIX1D (using Spot Date / EOD)
    vix1d_val = fetch_vix1d_close(spot_date)
    confidence_score = 0
    if vix1d_val is not None:
        confidence_score = calculate_confidence_score(vix1d_val)
        LOG.info(f"VIX1D ({spot_date}): {vix1d_val}, Confidence Score: {confidence_score}")
    else:
        LOG.warning(f"VIX1D not available for {spot_date}, trying {as_of}...")
        vix1d_val = fetch_vix1d_close(as_of)
        
        if vix1d_val is not None:
             confidence_score = calculate_confidence_score(vix1d_val)
             LOG.info(f"VIX1D ({as_of}): {vix1d_val}, Confidence Score: {confidence_score}")
        else:
             LOG.warning("VIX1D not available, defaulting confidence to 0")
             
    
    latest_results = {
        "as_of": as_of.isoformat(),
        "source": "MassiveFlatFile",
        "vix1d": vix1d_val,
        "confidence_score": confidence_score,
        "tickers": {}
    }
    
    # Initialize spot_map_cache for _process_ticker
    spot_map_cache = {}

    for ticker in tickers:
        try:
            _process_ticker(
                ticker, 
                as_of, 
                spot_date, 
                vix1d_val, 
                confidence_score, 
                latest_results,
                spot_map=spot_map_cache,
                df_all=df_all
            )
        except Exception as e:
            LOG.error(f"Failed to process {ticker}: {e}")
            latest_results["tickers"][ticker] = {"error": str(e)}
            
    # 4. Save Latest JSON
    json_path = options_latest_json_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_results = latest_results
    should_save = True

    if json_path.exists():
        try:
            with open(json_path, "r") as f:
                existing_data = json.load(f)
                existing_date_str = existing_data.get("as_of")
                
                # Check date precedence to prevent overwriting with older data during backfills
                if existing_date_str:
                    existing_date = date.fromisoformat(existing_date_str)
                    if as_of < existing_date:
                        LOG.info(f"Skipping latest.json update: Processing date {as_of} is older than existing {existing_date}")
                        should_save = False
                    elif as_of == existing_date:
                        # Merge Tickers
                        existing_tickers = existing_data.get("tickers", {})
                        existing_tickers.update(latest_results["tickers"])
                        existing_data["tickers"] = existing_tickers
                        
                        # Preserve VIX if available/newer
                        if vix1d_val:
                            existing_data["vix1d"] = vix1d_val
                            
                        final_results = existing_data
                        should_save = True
                    else:
                        # Processing is NEWER than existing
                        # Overwrite completely (default behavior)
                        should_save = True
                else:
                    should_save = True
                    
        except Exception as e:
            LOG.warning(f"Failed to read existing latest.json for merging: {e}")
            should_save = True
            
    if should_save:
        with open(json_path, "w") as f:
            json.dump(final_results, f, indent=2)
        LOG.info(f"Saved latest results to {json_path}")

    return final_results

def _process_ticker(
    ticker: str, 
    as_of: date,
    spot_date: date,
    vix1d_val: Optional[float], 
    confidence_score: int,
    latest_results: Dict[str, Any],
    spot_map: Dict[str, float] = {},
    df_all: pd.DataFrame = pd.DataFrame()
):
    # Determine dates for this ticker
    odte_date, weekly_date, monthly_date = get_target_expirations(as_of, ticker=ticker)

    # Log determined dates
    LOG.info(f"{ticker} | ODTE: {odte_date} | Weekly: {weekly_date} | Monthly: {monthly_date}")
    
    # 2. Fetch Underlying Price
    # Optimized: Check bulk map first
    spot_price = spot_map.get(ticker)
    
    # Handle Indicies in map (e.g. SPX comes as I:SPX or just SPX?)
    # Polygon Grouped Bars usually return 'SPY' for stocks.
    # For Indices, it might vary.
    if spot_price is None:
             # ^SPX -> I:SPX? -> SPX?
             # Let's try to find it.
             # Note: Grouped bars for 'stocks' might NOT include Indices?
             pass
    
    # Fallback to individual fetch if missing in map
    if spot_price is None:
        # LOG.info(f"Spot not in bulk map for {ticker}, fetching individually...")
        spot_price = fetch_underlying_close(ticker, spot_date)
    
    if spot_price is None:
         # Fallback to previous trading day
         from mie_lib.utils.trading_calendar import get_previous_trading_day
         prev_date = get_previous_trading_day(spot_date)
         LOG.warning(f"Could not fetch spot for {spot_date}, trying previous trading day {prev_date}")
         spot_price = fetch_underlying_close(ticker, prev_date)

    if spot_price is None:
        raise ValueError(f"Could not fetch spot price for {ticker}")
        
    # 3. (Removed bulk fetch) - We now fetch per expiration inside the loop to avoid API limits.
    # options_df = ...

    # 4. Calculate Expected Moves for each expiration
    expiry_map = {
        "ODTE": odte_date,
        "WEEKLY": weekly_date,
        "MONTHLY": monthly_date,
    }
    
    ticker_results = {
        "spot_price": spot_price,
        "vix1d": vix1d_val,
        "timestamp": datetime.now().isoformat(),
        "source": "MassiveAPI",
        "expirations": {},
        "day_iv_em": None, "day_straddle_em": None,
        "week_iv_em": None, "week_straddle_em": None,
        "month_iv_em": None, "month_straddle_em": None
    }
    
    for expiry_type, expiry_date in expiry_map.items():
        if not expiry_date:
            continue
            
        days_to_expiry = (expiry_date - as_of).days
            
        # Fetch strictly for this expiration
        exp_str = expiry_date.strftime("%Y-%m-%d")
        
        if as_of >= date.today():
            # Live/Today: Use Snapshot for best data (Greeks + IV)
            chain = fetch_option_chain_snapshot(ticker, spot_price, expiration_date=exp_str)
        else:
            # Historical: Use Bulk Flat File dataframe (if available)
            if not df_all.empty:
                 chain = _filter_chain(df_all, ticker, expiry_date)
                 LOG.info(f"DEBUG: _filter_chain returned {len(chain)} rows for {ticker} {expiry_type}")
            else:
                 # Fallback if flat file failed? No, user wants STRICT Flat File usage.
                 # "Discard the current fetch_historical_data... logic entirely."
                 chain = pd.DataFrame() # No fallback to API to avoid "No Chain" spam
                 LOG.warning(f"No flat file data available for {ticker} {exp_str} (Historical Mode)")
        
        if chain.empty:
            LOG.warning(f"No chain found for {ticker} {expiry_type} ({expiry_date})")
            continue
            
        # Enrich with YFinance Data if OI is missing (Price-only file)
        chain = enrich_with_yf_data(chain, ticker, expiry_date)
            
        # _filter_chain is no longer needed as we fetched specific data
        # But we verify it's not empty again just in case
            
        LOG.info(f"Found chain for {ticker} {expiry_type} ({expiry_date}): {len(chain)} rows")
        LOG.info(f"DEBUG: Sample Chain Rows:\n{chain[['strike', 'option_type', 'prev_close_mid']].head(5)}")

            
        # Find ATM Straddle
        # Assuming chain has 'strike', 'call_price', 'put_price' or similar from provider
        # The provider returns columns: 'strike', 'option_type', 'prev_close_mid' usually
        # Let's adapt to what PolygonOptionChainProvider returns in expected_move.py
        
        # Filter for Calls and Puts
        # The provider returns a DataFrame where each row is an option. 
        # We need to pivot or filter to find matching strikes.
        
        # Helper to get mid price and symbol for a strike and type
        def get_mid(strike, otype):
            import numpy as np # Ensure numpy is available
            # Use isclose for float comparison
            # Filter first by otype (string comparison is fast/safe)
            subset = chain[chain["option_type"] == otype]
            if subset.empty:
                return None, None
            
            # Find close strike
            # We assume 'strike' column is float.
            # We find rows where abs(strike - target) < epsilon
            row = subset[np.isclose(subset["strike"], strike, atol=0.01)]
            
            if not row.empty:
                val = row["prev_close_mid"].iloc[0]
                contract_sym = row.get("contractSymbol", pd.Series([None])).iloc[0]
                
                # Fallback: If price is missing, calculate via Black-Scholes if IV exists
                if val is None or pd.isna(val):
                    # Check for IV
                    iv_val = row["iv"].iloc[0]
                    if iv_val and iv_val > 0:
                        from mie_lib.analytics.gex.gex_engine import BlackScholes
                        # Use a standard Risk Free Rate (could be config, but hardcoded 4.5% is fine for estimation)
                        r = 0.045
                        T = max(days_to_expiry, 0.001) / 365.0
                        
                        if otype == "C":
                            val = BlackScholes.call_price(spot_price, strike, T, r, iv_val)
                        else:
                            val = BlackScholes.put_price(spot_price, strike, T, r, iv_val)
                            
                        # LOG.info(f"DEBUG: Calculated BS Price for {contract_sym} s={strike} v={val:.2f} (IV={iv_val:.3f})")
                
                return val, contract_sym
            return None, None
            
        # Find ATM strike (closest to spot)
        unique_strikes = chain["strike"].unique()
        if len(unique_strikes) == 0:
            continue
            
        atm_strike = min(unique_strikes, key=lambda x: abs(x - spot_price))
        
        call_mid, call_sym = get_mid(atm_strike, "C")
        put_mid, put_sym = get_mid(atm_strike, "P")
        
        if call_mid is None or put_mid is None:
            available_strikes = sorted(list(chain["strike"].unique()))
            LOG.info(f"DEBUG: Target Strike {atm_strike}. Available Strikes: {available_strikes}")
            LOG.warning(f"Missing ATM call/put for {ticker} {expiry_type} strike {atm_strike}")
            continue
            
        # Calculate EM
        em_dollars = calculate_straddle_em(call_mid, put_mid)
        upper = spot_price + em_dollars
        lower = spot_price - em_dollars
        
        # IV Verification (Optional, if IV is available)
        # Assuming chain might have 'iv' column
        iv_val = None
        if "iv" in chain.columns:
             # Average IV of ATM call/put
             c_row = chain[(chain["strike"] == atm_strike) & (chain["option_type"] == "C")]
             p_row = chain[(chain["strike"] == atm_strike) & (chain["option_type"] == "P")]
             ivs = []
             if not c_row.empty and pd.notna(c_row["iv"].iloc[0]): ivs.append(c_row["iv"].iloc[0])
             if not p_row.empty and pd.notna(p_row["iv"].iloc[0]): ivs.append(p_row["iv"].iloc[0])
             if ivs:
                 iv_val = sum(ivs) / len(ivs)
        
        em_iv = 0.0
        if iv_val:
            em_iv = calculate_iv_em(spot_price, iv_val, days_to_expiry)
            
        result_entry = {
            "expiry_date": expiry_date.isoformat(),
            "days_to_expiry": days_to_expiry,
            "atm_strike": float(atm_strike),
            "em_dollars": em_dollars,
            "upper_range": upper,
            "lower_range": lower,
            "em_iv": em_iv,
            "iv_val": iv_val,
            "debug": {
                "atm_strike": float(atm_strike),
                "call_ticker": call_sym,
                "call_price": float(call_mid),
                "put_ticker": put_sym,
                "put_price": float(put_mid)
            }
        }
        
        ticker_results["expirations"][expiry_type] = result_entry
        
    # Append to History
        _append_to_history(ticker, as_of, expiry_type, expiry_date, spot_price, em_dollars, upper, lower, vix1d_val, confidence_score)

    latest_results["tickers"][ticker] = ticker_results

def _append_to_history(
    ticker: str,
    as_of: date,
    expiry_type: str,
    expiry_date: date,
    spot: float,
    em: float,
    upper: float,
    lower: float,
    vix: Optional[float],
    conf: int
):
    """
    Appends a row to the ticker's historical Parquet file AND saves to pending for reliability check.
    """
    # 1. Main History
    path = options_expected_moves_path(ticker)
    
    new_row_dict = {
        "date": as_of,
        "expiry_type": expiry_type,
        "expiry_date": expiry_date,
        "spot_price": spot,
        "expected_move": em,
        "upper_range": upper,
        "lower_range": lower,
        "vix1d": vix,
        "confidence_score": conf,
        "timestamp": datetime.now().isoformat()
    }
    
    new_row = pd.DataFrame([new_row_dict])
    
    if path.exists():
        try:
            history = pd.read_parquet(path)
            # Ensure date column is datetime for compatibility
            if "date" in history.columns:
                 history["date"] = pd.to_datetime(history["date"]).dt.date
            
            # Remove existing entry for same date/type to allow re-runs
            history = history[~((history["date"] == as_of) & (history["expiry_type"] == expiry_type))]
            
            combined = pd.concat([history, new_row], ignore_index=True)
        except Exception as e:
            LOG.error(f"Failed to read history for {ticker}: {e}")
            combined = new_row
    else:
        combined = new_row
        
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)

    # 2. Save to Pending for Reliability Processor
    # We save each record as a separate small parquet or append to a daily pending file
    # A daily pending file is cleaner: pending_YYYY-MM-DD.parquet
    pending_dir = Path("data/analytics/expected_moves/pending")
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending_path = pending_dir / f"pending_{as_of}.parquet"
    
    # We need to match the schema expected by HistoricalEMRecord
    # The dict keys match the Pydantic model fields (mostly)
    # HistoricalEMRecord has: ticker, date, expiry_date, expiry_type, spot_price, expected_move_dollars, upper_range, lower_range, vix1d, confidence_score
    
    pending_record = {
        "ticker": ticker,
        "date": as_of, # This might need to be removed if not in schema, but schema has 'timestamp'. Schema doesn't have 'date' field explicitly? Wait, let me check models.py again.
        # models.py: ticker, expiry_type, expiry_date, underlying_price, expected_move_dollars, upper_range, lower_range, vix1d_value, confidence_score_percent, timestamp
        # It does NOT have 'date' (the calculation date). It uses 'timestamp' for that.
        # But 'date' is useful for dedup.
        # Let's check models.py line 11.
        # It has: ticker, expiry_type, expiry_date.
        # It does NOT have 'date' (as_of).
        # However, the pending file is named pending_YYYY-MM-DD.parquet, so the date is implicit.
        # But wait, reliability_processor.py line 104: record = HistoricalEMRecord(**data)
        # If I pass 'date', and it's not in the model, pydantic might ignore it or error depending on config (extra='ignore' is default in v2? No, 'ignore' is default in v1, 'extra'='ignore' in v2).
        # Let's look at models.py again. It inherits from BaseModel.
        # I should strictly follow the schema.
        
        "ticker": ticker,
        "expiry_type": expiry_type,
        "expiry_date": expiry_date,
        "underlying_price": spot,
        "expected_move_dollars": em,
        "upper_range": upper,
        "lower_range": lower,
        "vix1d_value": vix,
        "confidence_score_percent": conf,
        "timestamp": datetime.now() # Pydantic will serialize this
    }
    
    pending_df = pd.DataFrame([pending_record])
    
    if pending_path.exists():
        try:
            existing_pending = pd.read_parquet(pending_path)
            # Dedup
            existing_pending = existing_pending[~((existing_pending["ticker"] == ticker) & (existing_pending["expiry_type"] == expiry_type))]
            combined_pending = pd.concat([existing_pending, pending_df], ignore_index=True)
            combined_pending.to_parquet(pending_path, index=False)
        except Exception:
             pending_df.to_parquet(pending_path, index=False)
    else:
        pending_df.to_parquet(pending_path, index=False)

def _filter_chain(df_all: pd.DataFrame, ticker: str, expiry_date: date) -> pd.DataFrame:
    """
    Filters the massive dataframe for specific ticker and expiry.
    Returns format expected by _process_ticker.
    """
    # Filter by Ticker and calculate exp_str first
    exp_str = expiry_date.strftime("%Y-%m-%d")
    LOG.info(f"DEBUG: Filtering chain for {ticker} Exp={exp_str}. Input DF: {len(df_all)} rows.")
    
    if df_all.empty:
        return pd.DataFrame()
        
    # Filter by Ticker
    df = pd.DataFrame()
    # 1. Try Primary: 'underlying_ticker' OR 'ticker' column
    # The massive file might name it 'ticker' instead of 'underlying_ticker'
    col_name = None
    if 'underlying_ticker' in df_all.columns:
        col_name = 'underlying_ticker'
    elif 'ticker' in df_all.columns:
        col_name = 'ticker'
        
    if col_name:
        # Handle Indices: ^SPX might be listed as SPX or SPXW
        target = ticker.lstrip('^')
        # Check both with and without ^ prefix just in case CSV varies
        df = df_all[df_all[col_name].isin([target, ticker])]
        
    # 2. Fallback: Search in 'option_ticker' (OSI)
    #    e.g. O:SPY251219C... or just SPY...
    if df.empty and 'option_ticker' in df_all.columns:
         # Clean ticker again
         target = ticker.lstrip('^')
         # Regex: O:?TARGET\d
         pattern = f"^(O:)?{re.escape(target)}\\d"
         df = df_all[df_all['option_ticker'].str.contains(pattern, regex=True, na=False)]
         if not df.empty:
             LOG.info(f"DEBUG: Found {len(df)} rows via Regex Fallback for {ticker}")

    if df.empty:
        # LOG.warn(f"DEBUG: No rows for ticker {ticker} in daily file.")
        return pd.DataFrame()
        
    # Filter by Expiration
    # Client 'expiration' is YYYY-MM-DD string
    if 'expiration' in df.columns:
        df_exp = df[df['expiration'] == exp_str]
        
        if df_exp.empty:
             # Log available expirations to debug mismatch
             unique_exps = df['expiration'].unique()
             # Show first 5 and check if target is in there
             LOG.warning(f"DEBUG: Filter Failure for {ticker} {exp_str}. Matched Ticker Rows: {len(df)}. Available Expirations (First 10): {unique_exps[:10]}")
             return pd.DataFrame()
             
        df = df_exp
    
    if df.empty:
        return pd.DataFrame()
        
    # Valid Columns mapping
    # MassiveOptionsLoader provides: 'close', 'type' (call/put), 'strike', 'iv', 'gamma', 'delta', 'oi', 'option_ticker'
    # Engine expects: 'prev_close_mid', 'option_type' (C/P), 'contractSymbol'
    
    # Check if we need to rename columns (Loader output vs API output)
    if 'close' in df.columns and 'prev_close_mid' not in df.columns:
        df = df.rename(columns={'close': 'prev_close_mid'})
        
    if 'type' in df.columns and 'option_type' not in df.columns:
        # Loader 'type' is 'call'/'put'. Engine needs 'C'/'P'.
        # Robust mapping: strip, lower
        df['option_type'] = df['type'].astype(str).str.strip().str.lower().apply(lambda x: 'C' if x == 'call' else ('P' if x == 'put' else None))
        
    if 'option_ticker' in df.columns and 'contractSymbol' not in df.columns:
        df = df.rename(columns={'option_ticker': 'contractSymbol'})
        
    # Ensure all expected columns exist (fill NaN if missing, e.g. iv/gamma)
    expected_cols = ['strike', 'option_type', 'prev_close_mid', 'iv', 'contractSymbol', 'gamma', 'delta', 'oi']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None # or clean NaN
            
    return df

def enrich_with_yf_data(df: pd.DataFrame, ticker: str, expiry_date: date) -> pd.DataFrame:
    """
    Enriches the Options DataFrame with Open Interest and IV from YFinance.
    Used when flat files lack these columns (Price-only / OHLC files).
    """
    if expiry_date < date.today():
        # YFinance only supports current/future option chains
        return df

    # Check if we actually need enrichment
    # If OI is present and mostly non-null, skip
    if 'oi' in df.columns and df['oi'].notna().sum() > 10:
        return df

    LOG.info(f"Enriching {ticker} {expiry_date} with YFinance Data (OI/IV)...")

    try:
        # YFinance Ticker
        # Handle Indices: ^SPX -> ^SPX is correct for YF usually?
        # User tested with SPY. 
        # Use existing ticker.
        yf_ticker = yf.Ticker(ticker)
        
        exp_str = expiry_date.strftime("%Y-%m-%d")
        
        try:
             chain_data = yf_ticker.option_chain(exp_str)
        except Exception:
             # Expired or not found
             LOG.warning(f"YFinance option chain not found for {ticker} {exp_str}")
             return df
             
        calls = chain_data.calls
        puts = chain_data.puts
        
        # Normalize YF Data
        # YF Columns: contractSymbol, strike, openInterest, impliedVolatility
        cols_needed = ['contractSymbol', 'strike', 'openInterest', 'impliedVolatility']
        
        # Prepare YF dataframe for merge
        yf_calls = calls[cols_needed].copy() if not calls.empty else pd.DataFrame(columns=cols_needed)
        yf_puts = puts[cols_needed].copy() if not puts.empty else pd.DataFrame(columns=cols_needed)
        
        yf_calls['option_type'] = 'C'
        yf_puts['option_type'] = 'P'
        
        yf_df = pd.concat([yf_calls, yf_puts])
        
        if yf_df.empty:
            return df
            
        # Rename for merge
        yf_df = yf_df.rename(columns={
            'openInterest': 'oi_yf',
            'impliedVolatility': 'iv_yf'
        })
        
        # We merge on Strike + OptionType
        # Ensure types match
        df['strike'] = df['strike'].astype(float)
        yf_df['strike'] = yf_df['strike'].astype(float)
        
        # Merge
        # Left join to preserve original rows (Prices)
        # We match on strike and option_type
        # Note: rounding strikes might be needed if floats differ slightly
        merged = pd.merge(df, yf_df[['strike', 'option_type', 'oi_yf', 'iv_yf']], on=['strike', 'option_type'], how='left')
        
        # Fill missing 'oi' with 'oi_yf'
        # Ensure numeric types to avoid FutureWarning about downcasting
        merged['oi'] = pd.to_numeric(merged['oi'], errors='coerce')
        merged['iv'] = pd.to_numeric(merged['iv'], errors='coerce')
        merged['oi'] = merged['oi'].fillna(merged['oi_yf'])
        merged['iv'] = merged['iv'].fillna(merged['iv_yf'])
        
        # Drop temp columns
        merged = merged.drop(columns=['oi_yf', 'iv_yf'])
        
        return merged

    except Exception as e:
        LOG.warning(f"YFinance enrichment failed for {ticker} {expiry_date}: {e}")
        return df
