import pandas as pd
import pandas_market_calendars as mcal
from datetime import date, timedelta, datetime
from functools import lru_cache
from typing import Any
import calendar

# We use the NYSE exchange as a proxy for US equity trading days
NYSE = mcal.get_calendar('NYSE')

@lru_cache(maxsize=1)
def _get_trading_days(start_date: date, end_date: date) -> pd.DatetimeIndex:
    """Caches the official trading days for a given period."""
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    # Generate the calendar schedule for the period
    schedule = NYSE.schedule(start_date=start_date, end_date=end_date)
    
    # Return only the market open timestamps, normalized to date
    return schedule.index.normalize()

def is_trading_day(dt: date) -> bool:
    """Checks if a given date is an official trading day (excluding weekends/holidays)."""
    # Use a wide cache range to avoid recomputing the calendar frequently
    # Caching from 10 years ago to 1 year in the future
    wide_start = date.today() - timedelta(days=365 * 10)
    wide_end = date.today() + timedelta(days=365)
    
    trading_days = _get_trading_days(wide_start, wide_end)
    # Check against the date objects in the index
    return dt in trading_days.date

def is_verified_trading_day(dt: date) -> bool:
    """
    Strictly checks if a date is a trading day using YFinance data verification.
    Required to avoid 'No Chain Found' errors on holidays/weekends during backfill.
    """
    # Check 1: Weekend
    if dt.weekday() >= 5: # Saturday=5, Sunday=6
        return False
        
    # Check 2: Holiday/Market Open Verification via YFinance (SPY proxy)
    # Special Case: If dt is Today, we assume it's valid if it's a weekday.
    # YFinance might return empty for Today if market just opened or data is delayed.
    if dt == date.today():
         return True
         
    import yfinance as yf
    try:
        # Download 1 day of data. 
        # Note: For 'Today', this might be empty if market hasn't opened/settled?
        # But for backfilling (primary use case), it's accurate.
        data = yf.download("SPY", start=dt, end=dt + timedelta(days=1), progress=False)
        return not data.empty
    except Exception:
        # If network fails, default to conservative False (skip) or fallback?
        # User instruction implies strict check.
        return False

def get_next_trading_day(dt: date) -> date:
    """Finds the next market trading day."""
    dt += timedelta(days=1)
    while not is_trading_day(dt):
        dt += timedelta(days=1)
    return dt

def get_previous_trading_day(dt: date) -> date:
    """Finds the previous market trading day."""
    dt -= timedelta(days=1)
    while not is_trading_day(dt):
        dt -= timedelta(days=1)
    return dt

def get_trading_days_ahead(dt: date, days: int) -> date:
    """Finds the date that is N trading days in the future."""
    count = 0
    curr = dt
    # If today is not a trading day, don't count it. 
    # But usually dt is a trading day or today.
    while count < days:
        curr += timedelta(days=1)
        if is_trading_day(curr):
            count += 1
    return curr

# Aliases for compatibility
next_trading_day = get_next_trading_day
previous_trading_day = get_previous_trading_day

def last_trading_day_of_week(dt: date) -> date:
    """Returns the last trading day of the current week (usually Friday)."""
    start_of_week = dt - timedelta(days=dt.weekday())
    friday = start_of_week + timedelta(days=4)
    # If Friday is not a trading day, go back until we find one
    while not is_trading_day(friday):
        friday -= timedelta(days=1)
    return friday

def last_trading_day_of_next_week(dt: date) -> date:
    """Returns the last trading day of the next week."""
    # Move to next week's Monday
    next_week_start = dt + timedelta(days=7 - dt.weekday())
    return last_trading_day_of_week(next_week_start)

def last_trading_day_of_previous_week(dt: date) -> date:
    """Returns the last trading day of the previous week."""
    # Move to previous week's Monday
    prev_week_start = dt - timedelta(days=dt.weekday() + 7)
    return last_trading_day_of_week(prev_week_start)

def last_trading_day_of_month(year: int, month: int) -> date:
    """Returns the last trading day of the specified month."""
    last_day = calendar.monthrange(year, month)[1]
    dt = date(year, month, last_day)
    while not is_trading_day(dt):
        dt -= timedelta(days=1)
    return dt

def is_up_to_date(last_data_date: date, check_date: date = date.today()) -> tuple[bool, int]:
    """
    Checks data freshness by comparing the last data date to the previous trading day 
    relative to check_date (usually today).
    
    Returns (is_fresh, days_missing).
    """
    if last_data_date >= check_date:
        return True, 0

    # 1. Find the last trading day BEFORE the check_date (usually today)
    # If today is a weekend, previous_trading_day(today) is Friday.
    last_trading_day = get_previous_trading_day(check_date)
    
    if last_data_date >= last_trading_day:
        # Data is fresh if it covers the last trading day (or later)
        return True, 0
    else:
        # Data is missing. Count how many trading days are missing since last_data_date
        
        # Build list of missing trading dates
        missing_days = []
        current_date = last_trading_day
        while current_date > last_data_date:
            if is_trading_day(current_date):
                missing_days.append(current_date)
            current_date -= timedelta(days=1)
            
        # If the missing days count is high, it likely means the API hasn't run in a while.
        # We cap the missing days count at 5 for practical reporting purposes.
        return False, min(len(missing_days), 5) 

# Ensure 'date' objects are returned for consistency
def coerce_to_date(dt: Any) -> date:
    if isinstance(dt, datetime): return dt.date()
    if isinstance(dt, date): return dt
    try: return datetime.strptime(str(dt).split('T')[0], '%Y-%m-%d').date()
    except: return date.today()
