import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
import logging
from typing import List, Dict, Optional

from mie_lib.analytics.expected_moves.models import HistoricalEMRecord, RealizedOHLC
from mie_lib.utils.trading_calendar import is_trading_day, get_next_trading_day, last_trading_day_of_week, last_trading_day_of_month
from mie_lib.analytics.expected_moves.core import calculate_iv_em, calculate_confidence_score
from mie_lib.utils.paths import options_expected_moves_path

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
VOLATILITY_MAP = {
    "SPY": {"default": "^VIX", "0DTE": "^VIX1D", "WEEKLY": "^VIX9D"},
    "SPX": {"default": "^VIX", "0DTE": "^VIX1D", "WEEKLY": "^VIX9D"},
    "QQQ": {"default": "^VXN", "0DTE": "^VXN", "WEEKLY": "^VXN"}, # VXN variants might not exist on Yahoo
    "NQ":  {"default": "^VXN", "0DTE": "^VXN", "WEEKLY": "^VXN"},
    "DIA": {"default": "^VXD", "0DTE": "^VXD", "WEEKLY": "^VXD"},
    "IWM": {"default": "^VIX", "0DTE": "^VIX", "WEEKLY": "^VIX"}, # Fallback as RVX is missing
}

def fetch_history(tickers: List[str], start_date: date) -> pd.DataFrame:
    """Fetches historical data for multiple tickers."""
    data = yf.download(tickers, start=start_date, progress=False, auto_adjust=False)
    # Flatten MultiIndex if necessary or handle it
    # yfinance returns MultiIndex columns (Price, Ticker)
    return data

def get_vol_ticker(ticker: str, expiry_type: str) -> str:
    """Returns the appropriate volatility ticker."""
    mapping = VOLATILITY_MAP.get(ticker, VOLATILITY_MAP["SPY"])
    return mapping.get(expiry_type, mapping["default"])

def run_backfill(tickers: List[str] = ["SPY", "QQQ", "DIA", "IWM"]):
    """
    Backfills Expected Moves data.
    - 30 days for 0DTE
    - 10 weeks for Weekly
    - 4 months for Monthly
    """
    # Determine start date (approx 14 months ago to cover 1 year monthly)
    start_date = date.today() - timedelta(days=420)
    
    # Collect all necessary tickers (Underlying + Volatility)
    all_tickers = set(tickers)
    for t in tickers:
        mapping = VOLATILITY_MAP.get(t, VOLATILITY_MAP["SPY"])
        all_tickers.add(mapping["default"])
        all_tickers.add(mapping.get("0DTE", mapping["default"]))
        all_tickers.add(mapping.get("WEEKLY", mapping["default"]))
        
    logger.info(f"Fetching history for: {all_tickers} from {start_date}")
    
    try:
        history = fetch_history(list(all_tickers), start_date)
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return

    # Process each ticker
    for ticker in tickers:
        logger.info(f"Processing backfill for {ticker}...")
        
        records = []
        
        # We iterate through trading days in the history
        # history.index is DatetimeIndex
        trading_days = history.index.unique().sort_values()
        
        # --- 1. Backfill 0DTE (Last 90 Trading Days) ---
        target_days_0dte = trading_days[-95:] # Buffer
        
        for ts in target_days_0dte:
            as_of = ts.date()
            if as_of >= date.today(): continue # Don't backfill today/future
            
            # Determine Expiry: Next Trading Day
            expiry_date = get_next_trading_day(as_of)
            
            _process_single_backfill(ticker, as_of, "ODTE", expiry_date, history, records)

        # --- 2. Backfill Weekly (Last 26 Weeks) ---
        # Find last 28 Fridays
        fridays = [d for d in trading_days if d.weekday() == 4][-28:]
        for i in range(len(fridays) - 1):
            calc_date_ts = fridays[i] # Calculation Date (Friday Close)
            expiry_date_ts = fridays[i+1] # Expiration Date (Next Friday)
            
            as_of = calc_date_ts.date()
            expiry_date = expiry_date_ts.date()
            
            if as_of >= date.today(): continue
            
            _process_single_backfill(ticker, as_of, "WEEKLY", expiry_date, history, records)

        # --- 3. Backfill Monthly (Last 12 Months) ---
        # Find last 13 Month Ends
        
        processed_months = set()
        for ts in reversed(trading_days):
            d = ts.date()
            # Check if d is the last trading day of its month
            # We can check if get_next_trading_day(d).month != d.month
            next_trading = get_next_trading_day(d)
            if next_trading.month != d.month:
                # It is the last trading day of the month
                if len(processed_months) >= 13: break
                
                # This is the calculation date. Expiry is the NEXT month's last trading day.
                expiry_date = last_trading_day_of_month(next_trading.year, next_trading.month)
                
                if d >= date.today(): continue
                
                _process_single_backfill(ticker, d, "MONTHLY", expiry_date, history, records)
                processed_months.add((d.year, d.month))

        # --- Save Records ---
        if records:
            _save_backfill_records(ticker, records)
            logger.info(f"Saved {len(records)} backfilled records for {ticker}")

def _process_single_backfill(ticker, as_of, expiry_type, expiry_date, history, records):
    try:
        # 1. Get Spot Price
        # history['Close'][ticker]
        try:
            spot = history['Close'][ticker].loc[pd.Timestamp(as_of)]
        except:
            return # Missing data

        # 2. Get IV (Vol Index)
        vol_ticker = get_vol_ticker(ticker, expiry_type)
        try:
            iv_val = history['Close'][vol_ticker].loc[pd.Timestamp(as_of)]
        except:
            # Fallback to default VIX if specific failed
            try:
                iv_val = history['Close']["^VIX"].loc[pd.Timestamp(as_of)]
            except:
                return

        # 3. Calculate EM
        days_to_expiry = (expiry_date - as_of).days
        if days_to_expiry <= 0: return
        
        # FIX: Scale IV by 100 (e.g. 20.0 -> 0.20)
        em_dollars = calculate_iv_em(spot, iv_val / 100.0, days_to_expiry)
        upper = spot + em_dollars
        lower = spot - em_dollars
        
        # 4. Get Realized Close (if available)
        realized_ohlc = None
        closed_within = None
        high_breach_amt = None
        high_breach_pct = None
        low_breach_amt = None
        low_breach_pct = None
        
        if expiry_date < date.today():
            # Fetch realized close from history
            # We need to ensure history covers the expiry date
            try:
                r_close = history['Close'][ticker].loc[pd.Timestamp(expiry_date)]
                r_high = history['High'][ticker].loc[pd.Timestamp(expiry_date)]
                r_low = history['Low'][ticker].loc[pd.Timestamp(expiry_date)]
                r_open = history['Open'][ticker].loc[pd.Timestamp(expiry_date)]
                
                realized_ohlc = RealizedOHLC(open=r_open, high=r_high, low=r_low, close=r_close)
                
                # Calc Reliability
                closed_within = (r_close >= lower) and (r_close <= upper)
                
                high_breach_amt = max(0.0, r_high - upper)
                high_breach_pct = (high_breach_amt / em_dollars * 100) if em_dollars > 0 else 0
                
                low_breach_amt = max(0.0, lower - r_low)
                low_breach_pct = (low_breach_amt / em_dollars * 100) if em_dollars > 0 else 0
                
            except:
                pass # Realized data missing (maybe future or gap)

        # 5. Create Record
        # Confidence Score
        conf = calculate_confidence_score(iv_val) # Using IV as proxy for VIX1D for scoring
        
        record = HistoricalEMRecord(
            ticker=ticker,
            expiry_type=expiry_type,
            expiry_date=expiry_date,
            underlying_price=spot,
            expected_move_dollars=em_dollars,
            upper_range=upper,
            lower_range=lower,
            vix1d_value=iv_val, # Storing the used IV here
            confidence_score_percent=conf,
            timestamp=datetime.combine(as_of, datetime.min.time()),
            realized_ohlc=realized_ohlc,
            closed_within_em=closed_within,
            high_breach_amount=high_breach_amt,
            high_breach_percent=high_breach_pct,
            low_breach_amount=low_breach_amt,
            low_breach_percent=low_breach_pct
        )
        records.append(record)
        
    except Exception as e:
        logger.error(f"Error in single backfill {ticker} {as_of}: {e}")

def _save_backfill_records(ticker, records):
    """Saves records to the archive parquet."""
    path = options_expected_moves_path(ticker)
    
    new_df = pd.DataFrame([r.model_dump() for r in records])
    
    # Clean up dates for parquet
    new_df["expiry_date"] = pd.to_datetime(new_df["expiry_date"]).dt.date
    new_df["timestamp"] = new_df["timestamp"].astype(str) # Serialize datetime
    
    # OVERWRITE for backfill correction
    path.parent.mkdir(parents=True, exist_ok=True)
    new_df.to_parquet(path, index=False)

if __name__ == "__main__":
    run_backfill()
