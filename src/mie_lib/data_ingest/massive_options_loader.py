import pandas as pd
import numpy as np
from datetime import datetime, date
import logging
import re
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

class MassiveOptionsLoader:
    """
    Loader for Massive.com Options Flat Files (Day Aggregates).
    Expected CSV Schema includes:
    day, underlying_ticker, option_ticker, open_interest, implied_volatility, gamma, delta, ...
    """

    def __init__(self, data_dir: str = "data/raw/massive/options"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_day_aggregates(self, date_str: str, tickers: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Loads the daily aggregate CSV for a specific date.
        
        Args:
            date_str: "YYYY-MM-DD"
            tickers: Optional list of underlying tickers to filter (e.g. ["SPY", "QQQ"])
            
        Returns:
            pd.DataFrame with standardized columns for GEX Engine.
        """
        filename = f"options_{date_str}.csv"
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            logger.error(f"Flat file not found: {filepath}")
            return pd.DataFrame()
            
        try:
            # Read CSV
            df = pd.read_csv(filepath)
            
            # Filter by Underlying Ticker
            if tickers:
                target_tickers = [t.upper() for t in tickers]
                df = df[df['underlying_ticker'].isin(target_tickers)].copy()
                
            if df.empty:
                logger.warning(f"No data found for tickers {tickers} in {filename}")
                return pd.DataFrame()
                
            # Parse Option Ticker (OSI Format) if separate columns are missing
            if 'expiration' not in df.columns or 'type' not in df.columns or 'strike' not in df.columns:
                df = self._parse_osi_tickers(df)
                
            # Rename/Standardize columns for GEX Engine
            # Map: open_interest -> oi, implied_volatility -> iv
            df = df.rename(columns={
                "open_interest": "oi",
                "implied_volatility": "iv"
            })
            
            # Ensure proper types
            df['strike'] = pd.to_numeric(df['strike'], errors='coerce')
            df['oi'] = pd.to_numeric(df['oi'], errors='coerce').fillna(0)
            df['iv'] = pd.to_numeric(df['iv'], errors='coerce').fillna(0)
            df['gamma'] = pd.to_numeric(df['gamma'], errors='coerce').fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load flat file {filepath}: {e}")
            return pd.DataFrame()

    def _parse_osi_tickers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parses OSI compliant option tickers into expiry, type, and strike.
        Format: TTT...YYMMDD[C/P]SSSSSSSS
        Example: SPY251219C00500000 -> SPY, 2025-12-19, Call, 500.00
        """
        regex = r"([A-Z]+)(\d{6})([CP])(\d{8})"
        
        def parse_row(ticker):
            match = re.search(regex, ticker)
            if match:
                yymmdd = match.group(2)
                type_char = match.group(3) # C or P
                strike_str = match.group(4)
                
                # Expiry
                year = int("20" + yymmdd[:2])
                month = int(yymmdd[2:4])
                day = int(yymmdd[4:6])
                expiry = f"{year}-{month:02d}-{day:02d}"
                
                # Type
                otype = "call" if type_char == 'C' else "put"
                
                # Strike (divide by 1000)
                strike = float(strike_str) / 1000.0
                
                return pd.Series([expiry, otype, strike])
            return pd.Series([None, None, None])
        
        parsed = df['option_ticker'].apply(parse_row)
        parsed.columns = ['expiration', 'type', 'strike']
        
        return pd.concat([df, parsed], axis=1)
