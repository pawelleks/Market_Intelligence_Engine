import pandas_market_calendars as mcal
from datetime import date, timedelta
from typing import Optional
import pandas as pd

class TradingDayCalendar:
    """
    Utility class for US Market trading day calculations.
    Handles holidays and weekends using the NYSE calendar.
    """
    def __init__(self):
        # Initialize the NYSE calendar
        self.nyse = mcal.get_calendar('NYSE')

    def is_trading_day(self, dt: date) -> bool:
        """Checks if a date is a valid trading day."""
        # Check a small window around the date to be efficient
        schedule = self.nyse.schedule(start_date=dt, end_date=dt)
        return not schedule.empty

    def get_next_trading_day(self, dt: date) -> date:
        """
        Returns the next valid US trading day after the input date.
        """
        # Start checking from the next day
        next_day = dt + timedelta(days=1)
        
        # Look ahead up to 10 days (covers any holiday/weekend combo)
        schedule = self.nyse.schedule(start_date=next_day, end_date=next_day + timedelta(days=10))
        
        if schedule.empty:
            # Fallback for extreme edge cases or data issues, though unlikely with 10 days
            # Recursive or wider search could go here
            return next_day 
            
        # Return the first day in the schedule
        return schedule.index[0].date()

    def get_next_weekly_expiry(self, dt: date) -> date:
        """
        Returns the next standard weekly expiration date (usually Friday) 
        on or after the input date, skipping holidays.
        
        Logic:
        1. Find the next Friday on or after 'dt'.
        2. If that Friday is a holiday, move back to Thursday.
        3. If Thursday is also a holiday (rare), move back to Wednesday.
        """
        # 1. Find the next Friday
        # 0=Mon, 4=Fri
        days_ahead = (4 - dt.weekday() + 7) % 7
        if days_ahead == 0 and dt.weekday() == 4:
            # If today is Friday, it counts as the expiry if it's a trading day?
            # Prompt says "on or after". So yes.
            next_friday = dt
        else:
            next_friday = dt + timedelta(days=days_ahead)
            
        # 2. Check if Friday is a trading day
        if self.is_trading_day(next_friday):
            return next_friday
            
        # 3. If not, move back to Thursday
        thursday = next_friday - timedelta(days=1)
        if self.is_trading_day(thursday):
            return thursday
            
        # 4. If Thursday is not (e.g. Thanksgiving?), move to Wednesday
        wednesday = thursday - timedelta(days=1)
        return wednesday
