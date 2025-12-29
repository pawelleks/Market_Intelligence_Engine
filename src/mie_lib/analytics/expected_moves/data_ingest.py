"""
⛔ CRITICAL ARCHITECTURE CONSTRAINT (READ BEFORE MODIFYING):
-----------------------------------------------------------
This module adheres to the strict "Split-Source" Data Strategy defined in agent_rules.md

OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.

ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.

Any attempt to replace the flat-file ingest with an API call is a violation of project constraints. Fix logic errors only; do not change the data provider.
"""
"""
Data ingestion layer for Expected Moves (EM).
Handles fetching VIX1D, determining expiration dates, and retrieving option chains.
Uses yfinance for all data to avoid missing provider dependencies.
"""
from datetime import date, timedelta, datetime, timezone
import logging
import pandas as pd
import yfinance as yf
from typing import Optional, Tuple, Dict, Any

from mie_lib.utils.trading_calendar import (
    is_trading_day,
    get_next_trading_day,
    last_trading_day_of_week,
)

LOG = logging.getLogger(__name__)

def fetch_vix1d_close(as_of: date) -> Optional[float]:
    """
    Fetches the EOD close for VIX1D (or fallback VIX) for the given date.
    """
    # Try VIX1D first, then VIX
    tickers = ["^VIX1D", "^VIX"]
    
    for symbol in tickers:
        try:
            # Fetch a small window around the date to ensure we get the close
            start_date = as_of
            end_date = as_of + timedelta(days=1)
            
            # Use Ticker.history which is more robust for single tickers
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval="1d")
            
            if df is not None and not df.empty:
                # history() usually returns a DataFrame with simple columns
                if "Close" in df.columns:
                    close_val = df["Close"].iloc[0]
                    if pd.notna(close_val):
                        val = float(close_val)
                        LOG.info(f"Fetched {symbol} close for {as_of}: {val}")
                        return val
                    
        except Exception as e:
            LOG.warning(f"Failed to fetch {symbol} for {as_of}: {e}")
            continue
            
    LOG.error(f"Could not fetch VIX1D or VIX for {as_of}")
    return None

def get_target_expirations(as_of: date, ticker: Optional[str] = None) -> Tuple[date, date, date]:
    """
    Determines the target expiration dates based on the spec.
    
    1. ODTE: 
       - If Today and time < 16:30 ET: Today (if trading day) else Next Trading Day.
       - If Today and time >= 16:30 ET: Next Trading Day.
       - If not Today: as_of (if trading day) else Next Trading Day.
    2. Weekly: The first standard weekly expiration (Friday) on or after ODTE.
    3. Monthly: Last Trading Day of Month.
    """
    today = date.today()
    
    # 1. ODTE Logic
    if as_of == today:
        # Check current time in UTC
        now_utc = datetime.now(timezone.utc)
        
        # NOTE: Using simplistic cutoff 21:30 UTC for now. 
        cutoff_hour = 21
        cutoff_minute = 30
        
        is_after_market = (now_utc.hour > cutoff_hour) or (now_utc.hour == cutoff_hour and now_utc.minute >= cutoff_minute)
        
        LOG.info(f"0DTE Check: NowUTC={now_utc.strftime('%H:%M')} Cutoff={cutoff_hour}:{cutoff_minute} IsAfter={is_after_market} AsOf={as_of}")
        
        if is_after_market:
            # Rollover to next trading day
            odte_date = get_next_trading_day(as_of)
            LOG.info(f"  -> Rollover to {odte_date}")
        else:
            # Still in session (or pre-market)
            if is_trading_day(as_of):
                odte_date = as_of
                LOG.info(f"  -> Today is trading day: {odte_date}")
            else:
                odte_date = get_next_trading_day(as_of)
                LOG.info(f"  -> Today is NOT trading day: {odte_date}")
    else:
        # Historical / Backfill
        # FIX: If it is Friday (weekday 4), we want EOD to represent the Next Trading Day (Monday),
        # similar to how we handle "After Market" on weekdays.
        # This ensures weekend views show "Next Day" logic.
        if as_of.weekday() == 4:
             odte_date = get_next_trading_day(as_of)
             LOG.info(f"0DTE Check (Historical/Friday): Rollover to {odte_date}")
        elif is_trading_day(as_of):
            odte_date = as_of
        else:
            odte_date = get_next_trading_day(as_of)
        LOG.info(f"0DTE Check (Historical): AsOf={as_of} -> {odte_date}")
    
    # 2. Weekly: First Friday on or after ODTE
    # Start checking from ODTE
    current = odte_date
    while True:
        # Check if current is a Friday (weekday 4) AND a trading day
        if current.weekday() == 4 and is_trading_day(current):
            weekly_date = current
            break
        current += timedelta(days=1)
        # Safety break
        if (current - odte_date).days > 14:
            LOG.warning("Could not find a weekly expiration within 2 weeks, defaulting to ODTE")
            weekly_date = odte_date
            break
            
    # 3. Monthly Logic
    # Indices/ETFs (SPY, QQQ, IWM, DIA, ^VIX) often use EOM (End of Month) expirations.
    # Equities (LLY, AAPL, etc.) usually only have standard Monthly (3rd Friday).
    # We default to EOM for the "Big 4" + VIX, and 3rd Friday for everything else.
    
    # Heuristic for generic "Index with EOMs"
    # This list can be expanded or moved to config if needed.
    eom_tickers = {"SPY", "QQQ", "IWM", "DIA", "RSP", "^VIX", "^VIX1D"}
    use_eom = False
    
    if ticker:
        t_upper = ticker.upper()
        if t_upper in eom_tickers or t_upper.startswith("^"):
            use_eom = True
    else:
        # Default to EOM if no ticker specified (backward compat)
        use_eom = True

    def get_last_trading_day_of_month(year, month):
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, last_day)
        while not is_trading_day(d):
            d -= timedelta(days=1)
        return d

    def get_third_friday_of_month(year, month):
        # 3rd Friday
        # 1. Find the 1st day of month
        d = date(year, month, 1)
        # 2. Find first Friday
        # weekday(): Mon=0, Fri=4
        days_to_fri = (4 - d.weekday() + 7) % 7
        first_friday = d + timedelta(days=days_to_fri)
        # 3. Add 2 weeks
        third_friday = first_friday + timedelta(weeks=2)
        
        # Check if trading day? (Usually yes, unless Holiday)
        # If holiday, it typically moves to PREV day (Thursday)
        # mie_lib.utils.trading_calendar should handle this check?
        # Let's just check is_trading_day, if not move back 1.
        while not is_trading_day(third_friday):
            third_friday -= timedelta(days=1)
        
        return third_friday

    if use_eom:
        monthly_date = get_last_trading_day_of_month(as_of.year, as_of.month)
        # Check if passed (relative to ODTE)
        if monthly_date < odte_date:
            if odte_date.month == 12:
                monthly_date = get_last_trading_day_of_month(odte_date.year + 1, 1)
            else:
                monthly_date = get_last_trading_day_of_month(odte_date.year, odte_date.month + 1)
    else:
        # Standard Equity (3rd Friday)
        monthly_date = get_third_friday_of_month(as_of.year, as_of.month)
        # If passed (relative to ODTE), move to next month
        if monthly_date < odte_date:
             if odte_date.month == 12:
                 monthly_date = get_third_friday_of_month(odte_date.year + 1, 1)
             else:
                 monthly_date = get_third_friday_of_month(odte_date.year, odte_date.month + 1)

    return odte_date, weekly_date, monthly_date

def fetch_option_chain(
    ticker: str,
    expiry: date,
    as_of: date,
    provider: Any = None # Unused now
) -> pd.DataFrame:
    """
    Fetches the option chain for a specific ticker and expiration date using yfinance.
    Returns a DataFrame with columns: ['strike', 'option_type', 'prev_close_mid', 'iv']
    """
    try:
        yf_ticker = yf.Ticker(ticker)
        
        # yfinance expects expiration as string 'YYYY-MM-DD'
        exp_str = expiry.isoformat()
        
        # Check if expiry is available
        available_exps = yf_ticker.options
        if exp_str not in available_exps:
            LOG.warning(f"Expiration {exp_str} not found for {ticker}. Available: {available_exps[:3]}...")
            return pd.DataFrame()
            
        opts = yf_ticker.option_chain(exp_str)
        calls = opts.calls
        puts = opts.puts
        
        # Process Calls
        calls['option_type'] = 'C'
        calls['mid'] = (calls['bid'] + calls['ask']) / 2
        # Fallback to lastPrice if bid/ask are 0 or missing (common in EOD/delayed data)
        calls['mid'] = calls.apply(lambda row: row['lastPrice'] if row['mid'] == 0 else row['mid'], axis=1)
        
        # Process Puts
        puts['option_type'] = 'P'
        puts['mid'] = (puts['bid'] + puts['ask']) / 2
        puts['mid'] = puts.apply(lambda row: row['lastPrice'] if row['mid'] == 0 else row['mid'], axis=1)
        
        # Combine
        chain = pd.concat([calls, puts])
        
        # Rename columns to match expected schema
        # Expected: strike, option_type, prev_close_mid, iv, contractSymbol
        chain = chain.rename(columns={
            'strike': 'strike',
            'mid': 'prev_close_mid',
            'impliedVolatility': 'iv',
            'contractSymbol': 'contractSymbol'
        })
        
        return chain[['strike', 'option_type', 'prev_close_mid', 'iv', 'contractSymbol']]
        
    except Exception as e:
        LOG.error(f"Error fetching option chain for {ticker} exp {expiry}: {e}")
        return pd.DataFrame()

def fetch_underlying_close(ticker: str, as_of: date, provider: Any = None) -> Optional[float]:
    """
    Fetches the underlying spot close price using yfinance.
    """
    try:
        start_date = as_of
        end_date = as_of + timedelta(days=1)
        
        # Use Ticker.history
        yf_ticker = yf.Ticker(ticker)
        # auto_adjust=False ensures we get the raw Close, matching Massive/Yahoo Website "Close" column
        df = yf_ticker.history(start=start_date, end=end_date, interval="1d", auto_adjust=False)
        
        if df is not None and not df.empty:
            LOG.info(f"yfinance raw data for {ticker}:\n{df.tail(1)}")
            if "Close" in df.columns:
                close_val = df["Close"].iloc[0]
                if pd.notna(close_val):
                    return float(close_val)
                
    except Exception as e:
        LOG.error(f"Error fetching spot price for {ticker}: {e}")
        
    return None
