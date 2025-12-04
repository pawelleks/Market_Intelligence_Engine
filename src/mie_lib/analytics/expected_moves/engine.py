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

from mie_lib.analytics.expected_moves.core import (
    calculate_straddle_em,
    calculate_iv_em,
    calculate_confidence_score,
)
from mie_lib.analytics.expected_moves.data_ingest import (
    fetch_vix1d_close,
    get_target_expirations,
    fetch_option_chain,
    fetch_underlying_close,
)
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
    
    # 1. Fetch Global VIX1D
    vix1d_val = fetch_vix1d_close(as_of)
    confidence_score = 0
    if vix1d_val is not None:
        confidence_score = calculate_confidence_score(vix1d_val)
        LOG.info(f"VIX1D: {vix1d_val}, Confidence Score: {confidence_score}")
    else:
        LOG.warning("VIX1D not available, defaulting confidence to 0")
        
    latest_results = {
        "as_of": as_of.isoformat(),
        "vix1d": vix1d_val,
        "confidence_score": confidence_score,
        "tickers": {}
    }
    
    for ticker in tickers:
        try:
            _process_ticker(ticker, as_of, vix1d_val, confidence_score, latest_results)
        except Exception as e:
            LOG.error(f"Failed to process {ticker}: {e}")
            latest_results["tickers"][ticker] = {"error": str(e)}
            
    # 4. Save Latest JSON
    json_path = options_latest_json_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(latest_results, f, indent=2)
        
    LOG.info(f"Saved latest results to {json_path}")
    return latest_results

def _process_ticker(
    ticker: str, 
    as_of: date, 
    vix1d_val: Optional[float], 
    confidence_score: int,
    latest_results: Dict[str, Any]
):
    # 2. Fetch Underlying Price
    spot_price = fetch_underlying_close(ticker, as_of)
    if spot_price is None:
        raise ValueError(f"Could not fetch spot price for {ticker}")
        
    # 3. Determine Expirations
    odte_date, weekly_date, monthly_date = get_target_expirations(as_of)
    
    ticker_results = {
        "spot_price": spot_price,
        "expirations": {}
    }
    
    # Process each expiry type
    for expiry_type, expiry_date in [("ODTE", odte_date), ("WEEKLY", weekly_date), ("MONTHLY", monthly_date)]:
        days_to_expiry = (expiry_date - as_of).days
        
        # Fetch Chain
        chain = fetch_option_chain(ticker, expiry_date, as_of)
        
        if chain.empty:
            LOG.warning(f"No chain found for {ticker} {expiry_type} ({expiry_date})")
            continue
            
        # Find ATM Straddle
        # Assuming chain has 'strike', 'call_price', 'put_price' or similar from provider
        # The provider returns columns: 'strike', 'option_type', 'prev_close_mid' usually
        # Let's adapt to what PolygonOptionChainProvider returns in expected_move.py
        
        # Filter for Calls and Puts
        # The provider returns a DataFrame where each row is an option. 
        # We need to pivot or filter to find matching strikes.
        
        # Helper to get mid price and symbol for a strike and type
        def get_mid(strike, otype):
            row = chain[(chain["strike"] == strike) & (chain["option_type"] == otype)]
            if not row.empty:
                return row["prev_close_mid"].iloc[0], row.get("contractSymbol", pd.Series([None])).iloc[0]
            return None, None
            
        # Find ATM strike (closest to spot)
        unique_strikes = chain["strike"].unique()
        if len(unique_strikes) == 0:
            continue
            
        atm_strike = min(unique_strikes, key=lambda x: abs(x - spot_price))
        
        call_mid, call_sym = get_mid(atm_strike, "C")
        put_mid, put_sym = get_mid(atm_strike, "P")
        
        if call_mid is None or put_mid is None:
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
    Appends a row to the ticker's historical Parquet file.
    """
    path = options_expected_moves_path(ticker)
    
    new_row = pd.DataFrame([{
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
    }])
    
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
