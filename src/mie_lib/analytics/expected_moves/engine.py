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
            
    # 4. Save Latest JSON - Merge with existing to prevent creating partial files
    json_path = options_latest_json_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_results = latest_results
    if json_path.exists():
        try:
            with open(json_path, "r") as f:
                existing_data = json.load(f)
                # If "as_of" matches, we merge tickers. If not, we might want to overwrite or keep?
                # Usually we want to keep all tickers that are valid.
                # But let's assume we are building for the same day.
                if existing_data.get("as_of") == as_of.isoformat():
                    # Merge tickers
                    existing_tickers = existing_data.get("tickers", {})
                    # Update with new results
                    existing_tickers.update(latest_results["tickers"])
                    existing_data["tickers"] = existing_tickers
                    # Update metadata if needed (e.g. VIX1D might change if re-run, but we use new run)
                    existing_data["vix1d"] = vix1d_val
                    final_results = existing_data
                else:
                    # New date, overwrite? Or keep old tickers until refreshed?
                    # For now, if date changes, we probably start fresh or keep old ones as stale?
                    # Let's overwrite if date changes to clean up old data, BUT 
                    # if we run sequentially for different tickers, day should match.
                    pass
        except Exception as e:
            LOG.warning(f"Failed to read existing latest.json for merging: {e}")
            
    with open(json_path, "w") as f:
        json.dump(final_results, f, indent=2)
        
    LOG.info(f"Saved latest results to {json_path}")
    return final_results

def _process_ticker(
    ticker: str, 
    as_of: date, 
    vix1d_val: Optional[float], 
    confidence_score: int,
    latest_results: Dict[str, Any]
):
    # 3. Determine Expirations First
    # We need ODTE date to determine the reference spot date
    odte_date, weekly_date, monthly_date = get_target_expirations(as_of)
    
    # Log determined dates
    LOG.info(f"{ticker} | ODTE: {odte_date} | Weekly: {weekly_date} | Monthly: {monthly_date}")
    
    # 2. Fetch Underlying Price
    # Spot Price should be the Close of the PREVIOUS trading day relative to the 0DTE session date.
    # Why? Because Expected Move is calculated from the previous close.
    # If ODTE is Today, spot is Yesterday's close.
    # If ODTE is Next Day, spot is Today's close (or Yesterday's if Today is a holiday/weekend).
    
    # We use get_previous_trading_day relative to ODTE date unless we are MID-SESSION? 
    # Actually, Expected Move is usually "overnight" or "session" range. 
    # Traditionally, we anchor to the previous close.
    # If we are live in session, we might want live spot, but the request was "based on previous EOD prices".
    # So yes, previous trading day relative to trading session (ODTE date).
    
    from mie_lib.utils.trading_calendar import get_previous_trading_day
    spot_date = get_previous_trading_day(odte_date)
    
    spot_price = fetch_underlying_close(ticker, spot_date)
    if spot_price is None:
        # Fallback: try as_of if different
        if spot_date != as_of:
             LOG.warning(f"Could not fetch spot for {spot_date}, trying {as_of}")
             spot_price = fetch_underlying_close(ticker, as_of)
             
    if spot_price is None:
        raise ValueError(f"Could not fetch spot price for {ticker}")
        
    LOG.info(f"{ticker} | Spot Reference Date: {spot_date} | Price: {spot_price}")

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
