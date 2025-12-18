import requests
import pandas as pd
import os
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class MassiveAPIClient:
    """
    Client for Massive.com / Polygon-compatible REST API.
    Used for fetching Option Chain Snapshots with Greeks.
    """
    
    BASE_URL = "https://api.massive.com/v3/snapshot/options"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
             logger.warning("No API Key found for Massive/Polygon (POLYGON_API_KEY).")

    def fetch_snapshot(self, ticker: str, 
                       min_strike: Optional[float] = None, 
                       max_strike: Optional[float] = None,
                       expiration_date: Optional[str] = None,
                       limit: int = 500) -> pd.DataFrame:
        """
        Fetches option chain snapshot for a ticker.
        """
        if not self.api_key:
            return pd.DataFrame()

        url = f"{self.BASE_URL}/{ticker.upper()}"
        params = {
            "apiKey": self.api_key,
            "limit": limit,
            # "order": "asc",       # Removing sort/order to avoid 400 Bad Request risks
            # "sort": "strike_price" # as observed in diagnostics.
        }
        
        # Add strike filters if provided
        if min_strike:
            params["strike_price.gte"] = min_strike
        if max_strike:
            params["strike_price.lte"] = max_strike
            
        # Add expiration filter
        if expiration_date:
            params["expiration_date"] = expiration_date
            
        logger.info(f"Fetching Massive Snapshot for {ticker} (Strikes: {min_strike}-{max_strike}, Exp: {expiration_date})...")
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch Massive snapshot for {ticker}: {e}")
            return pd.DataFrame()
            
        results = data.get("results", [])
        if not results:
            logger.warning(f"No results for {ticker} from Massive API.")
            return pd.DataFrame()
            
        # Parse Results into DataFrame
        records = []
        for item in results:
            details = item.get("details", {})
            greeks = item.get("greeks", {})
            day = item.get("day", {})
            
            rec = {
                "contractSymbol": details.get("ticker"), # mapped from option_ticker
                "expiration": details.get("expiration_date"),
                "strike": details.get("strike_price"),
                "option_type": "C" if details.get("contract_type") == "call" else "P", # mapped to C/P
                "iv": item.get("implied_volatility"),
                "delta": greeks.get("delta"),
                "gamma": greeks.get("gamma"),
                "theta": greeks.get("theta"),
                "vega": greeks.get("vega"),
                "prev_close_mid": day.get("close"), # mapped from close
                "volume": day.get("volume"),
                "oi": item.get("open_interest"),
                "underlying_ticker": item.get("underlying_asset", {}).get("ticker") # mapped from underlying
            }
            records.append(rec)
            
        df = pd.DataFrame(records)
        df = pd.DataFrame(records)
        return df

    def find_atm_contracts(self, ticker: str, expiration_date: str, atm_strike: float) -> List[Dict[str, Any]]:
        """
        Finds specific Call and Put contract tickers for the given ATM strike and expiration.
        Constraint: Used for Historical Backfill (Snapshot doesn't work).
        """
        url = "https://api.massive.com/v3/reference/options/contracts"
        params = {
            "underlying_ticker": ticker.upper(),
            "expiration_date": expiration_date,
            "strike_price": atm_strike, # Exact match for ATM
            "limit": 10,
            "apiKey": self.api_key
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results
        except Exception as e:
            logger.error(f"Failed to find contracts for {ticker} exp {expiration_date} strike {atm_strike}: {e}")
            return []

    def fetch_day_close(self, contract_ticker: str, date_str: str) -> Optional[float]:
        """
        Fetches the specific Close price for a contract on a specific date using Aggregates (Bars).
        Endpoint: /v2/aggs/ticker/{contract_ticker}/range/1/day/{date_str}/{date_str}
        """
        url = f"https://api.massive.com/v2/aggs/ticker/{contract_ticker}/range/1/day/{date_str}/{date_str}"
        params = {
            "apiKey": self.api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 1
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                return float(results[0].get("c")) # 'c' is Close
        except Exception as e:
             # Log warning but don't spam if just missing data
             pass
        return None

    def find_next_expiration(self, ticker: str, after_date: str) -> Optional[str]:
        """
        Finds the closest valid expiration date >= after_date.
        Useful for stocks that don't have daily expirations.
        """
        url = "https://api.massive.com/v3/reference/options/contracts"
        params = {
            "underlying_ticker": ticker.upper(),
            "expiration_date.gte": after_date,
            "sort": "expiration_date",
            "order": "asc",
            "limit": 1,
            "apiKey": self.api_key
        }
        try:
            resp = requests.get(url, params=params, timeout=5)
            # 404 is possible if no contracts found? Or empty results.
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                return results[0].get("expiration_date")
        except Exception as e:
            # logger.warning(f"Failed to resolve next expiration for {ticker}: {e}")
            pass
        return None

    def fetch_historical_atm_data(self, ticker: str, expiration_date: str, spot_price: float, as_of_date: str) -> pd.DataFrame:
        """
        Orchestrates historical data fetching for Expected Moves.
        1. Resolves Actual Expiration Date (Dynamic Lookup).
        2. Identifies ATM Strike.
        3. Finds Contract Tickers (Call/Put).
        4. Fetches Historical Close Prices.
        Returns a DataFrame mimicking the Snapshot schema.
        """
        # Step 0: Ticker Hygiene
        # Ignore unsupported indices
        if ticker in ["^SPX", "^NDX", "SPX", "NDX"]:
            # logger.info(f"Skipping unsupported index {ticker}")
            return pd.DataFrame() # We don't have subs for these
            
        clean_ticker = ticker.replace("^", "") if ticker not in ["^SPX", "^NDX"] else ticker
        
        # Step 1: Find Actual Expiration (Dynamic Lookup)
        start_search_date = expiration_date
        actual_expiry = self.find_next_expiration(clean_ticker, start_search_date)
        
        if not actual_expiry:
            logger.warning(f"No valid expiration found for {clean_ticker} starting from {expiration_date}")
            return pd.DataFrame()
            
        # logger.info(f"Resolved expiry for {ticker}: Requested {expiration_date} -> Found {actual_expiry}")
        
        # Step 2: Find ATM Contracts for this ACTUAL expiry
        url = "https://api.massive.com/v3/reference/options/contracts"
        
        # Widen search range to +/- 5% to ensure we catch strikes even in volatile moves
        min_strike = spot_price * 0.95
        max_strike = spot_price * 1.05
        
        logger.info(f"DEBUG: Searching chain for {clean_ticker} Exp={actual_expiry} Spot={spot_price} Range=[{min_strike:.2f}, {max_strike:.2f}]")
        
        params = {
            "underlying_ticker": clean_ticker.upper(),
            "expiration_date": actual_expiry, # Use resolved date
            "strike_price.gte": min_strike,
            "strike_price.lte": max_strike,
            "limit": 100, # Increased limit to capture enough candidates
            "apiKey": self.api_key
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            logger.info(f"DEBUG: API returned {len(results)} contracts for {clean_ticker}")
        except Exception as e:
            logger.error(f"Failed to fetch contract list: {e}")
            return pd.DataFrame()
            
        if not results:
            logger.warning(f"No contracts found for {clean_ticker} {actual_expiry} near {spot_price}")
            return pd.DataFrame()
            
        # Step 3: Return ALL Candidates (Discovery First)
        # Instead of pre-selecting ATM here, we return the full "Board" of candidates.
        # This allows the consumer (engine.py) to find the best match or fallback.
        # This mimics the "Snapshot" behavior which returns a full chain.
        
        records = []
        for t in results:
             symbol = t['ticker']
             ctype = "C" if t['contract_type'] == "call" else "P"
             strike = t['strike_price']
             
             # Fetch Price for each candidate?
             # WARNING: fetching price for 100 contracts -> 100 API calls?
             # That might be too slow for "Aggs" (1 call per contract).
             # The user instruction: "Fetch the Aggregates (Bars) for that specific contract."
             # implying we select ONE contract first?
             # User instruction: "Step 2: Best Match Selection (In Python)... Pick the winner... Step 3... Fetch Aggregates".
             # So we MUST select the ticker HERE if we want to save API calls.
             # Alternatively, we iterate until we find one with a price?
        
        # Re-reading User Plan:
        # "Step 1: Fetch Board... Step 2: Best Match Selection (In Python)... Step 3: Fetch Aggregates... for that specific contract".
        # So I *should* select the single best strike HERE, but do it robustly.
        
        # Robust Selection Logic:
        # 1. Sort by distance to spot
        sorted_results = sorted(results, key=lambda x: abs(x['strike_price'] - spot_price))
        
        if not sorted_results:
             return pd.DataFrame()
             
        # Select best candidates (Call and Put) for the closest strike
        best_strike = sorted_results[0]['strike_price']
        distance = abs(best_strike - spot_price)
        logger.info(f"DEBUG: Selected Strike {best_strike} (Distance: {distance:.2f}) from {len(results)} candidates.")
        
        # Get C/P for this best strike
        targets = [r for r in results if r['strike_price'] == best_strike]
        
        records = []
        for t in targets:
            symbol = t['ticker']
            ctype = "C" if t['contract_type'] == "call" else "P"
            
            # Fetch Price
            price = self.fetch_day_close(symbol, as_of_date)
            # If price is missing, we might return it as None or skip?
            # Snapshot returns None usually.
            
            rec = {
                "contractSymbol": symbol,
                "expiration": actual_expiry,
                "strike": best_strike,
                "option_type": ctype,
                "iv": None, 
                "prev_close_mid": price,
                "underlying_ticker": ticker
            }
            records.append(rec)
            
        return pd.DataFrame(records)

def fetch_option_chain_snapshot(ticker: str, spot_price: float, expiration_date: Optional[str] = None, volatility_buffer: float = 0.2) -> pd.DataFrame:
    """
    Helper to fetch chain with automatic strike filtering (Spot +/- 20%).
    """
    client = MassiveAPIClient()
    
    # Calculate strike range
    # Widen buffer to 50% (0.5) to ensure we get a "Board" of options,
    # reducing risk of missing ATM due to tight filters.
    if volatility_buffer < 0.5:
        volatility_buffer = 0.5
        
    min_strike = spot_price * (1 - volatility_buffer)
    max_strike = spot_price * (1 + volatility_buffer)
    
    return client.fetch_snapshot(ticker, min_strike=min_strike, max_strike=max_strike, expiration_date=expiration_date, limit=250)

def fetch_historical_option_chain(ticker: str, spot_price: float, expiration_date: str, as_of_date: str) -> pd.DataFrame:
    """
    Helper to fetch historical ATM options data.
    """
    client = MassiveAPIClient()
    return client.fetch_historical_atm_data(ticker, expiration_date, spot_price, as_of_date)
