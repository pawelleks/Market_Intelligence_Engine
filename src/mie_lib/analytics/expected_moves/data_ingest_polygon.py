"""
Data ingestion layer for Expected Moves (EM) via Polygon.io.
Handles fetching VIX1D, determining expiration dates, and retrieving option chains.
"""
import os
import requests
import time
import logging
import pandas as pd
from datetime import date, timedelta
from typing import Optional, Tuple, Any, List, Dict

# Re-export expiration logic (unchanged)
from mie_lib.analytics.expected_moves.data_ingest import get_target_expirations

LOG = logging.getLogger(__name__)

def _get_api_key() -> str:
    key = os.environ.get("POLYGON_API_KEY")
    if not key:
        raise ValueError("POLYGON_API_KEY not found in environment")
    return key

def fetch_vix1d_close(as_of: date) -> Optional[float]:
    """
    Fetches the EOD close for VIX1D (or fallback VIX) for the given date using Polygon.
    """
    api_key = _get_api_key()
    tickers = ["I:VIX1D", "I:VIX"]
    
    for symbol in tickers:
        try:
            # Polygon Aggregates API
            # /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{as_of}/{as_of}?adjusted=true&sort=asc&limit=120&apiKey={api_key}"
            
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    # results object has 'c' for close
                    close_val = results[0].get("c")
                    if close_val is not None:
                        LOG.info(f"Polygon fetched {symbol} close for {as_of}: {close_val}")
                        return float(close_val)
            else:
                LOG.warning(f"Polygon error fetching {symbol}: {resp.status_code} {resp.text}")
                
        except Exception as e:
            LOG.warning(f"Failed to fetch {symbol} from Polygon for {as_of}: {e}")
            continue
            
    LOG.error(f"Could not fetch VIX1D or VIX from Polygon for {as_of}")
    return None

def fetch_underlying_close(ticker: str, as_of: date, provider: Any = None) -> Optional[float]:
    """
    Fetches the underlying spot close price using Polygon.
    """
    api_key = _get_api_key()
    
    # Handle indices: ^SPX -> I:SPX calculation?
    # Usually inputs are SPY, QQQ. If input is ^GSPC, map to I:GSPC
    poly_ticker = ticker
    if ticker.startswith("^"):
        poly_ticker = "I:" + ticker.replace("^", "")
        
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{poly_ticker}/range/1/day/{as_of}/{as_of}?adjusted=true&sort=asc&limit=120&apiKey={api_key}"
        
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                close_val = results[0].get("c")
                if close_val is not None:
                    LOG.info(f"Polygon fetched spot {ticker} for {as_of}: {close_val}")
                    return float(close_val)
            else:
                 LOG.warning(f"No Polygon agg results for {ticker} on {as_of}")
        else:
            LOG.error(f"Polygon spot error {ticker}: {resp.status_code} {resp.text}")
            
    except Exception as e:
        LOG.error(f"Error fetching Polygon spot price for {ticker}: {e}")
        
    return None

def fetch_grouped_daily_bars(as_of: date) -> Dict[str, float]:
    """
    Fetches the daily Open/Close for ALL tickers in the US Market for a given date.
    Uses Polygon's Grouped Daily Bars endpoint (1 API call).
    Returns a dictionary mapping {ticker: close_price}.
    """
    api_key = _get_api_key()
    # /v2/aggs/grouped/locale/us/market/stocks/{date}
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{as_of}?adjusted=true&apiKey={api_key}"
    
    spot_map = {}
    try:
        LOG.info(f"Fetching bulk spot prices for {as_of} via Polygon Grouped Daily...")
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            for r in results:
                # Ticker 'T', Close 'c'
                t = r.get("T")
                c = r.get("c")
                if t and c is not None:
                    spot_map[t] = float(c)
            LOG.info(f"Fetched {len(spot_map)} spot prices.")
        else:
            LOG.error(f"Polygon Grouped Daily error: {resp.status_code} {resp.text}")
            
    except Exception as e:
        LOG.error(f"Error fetching bulk spot prices: {e}")
        
    return spot_map

def fetch_option_chain(
    ticker: str, 
    expiry: date, 
    as_of: date,
    provider: Any = None,
    spot_price: Optional[float] = None
) -> pd.DataFrame:
    """
    Fetches the option chain for a specific ticker and expiration date using Polygon Snapshot API.
    This fetches ALL contracts for the expiry in 1 request, which is much more efficient (prevents 429s).
    """
    api_key = _get_api_key()
    
    # Handle indices: ^SPX -> I:SPX
    api_ticker = ticker
    if ticker.startswith("^"):
        api_ticker = "I:" + ticker.replace("^", "")
    
    # URL for Snapshot options chain
    # https://api.polygon.io/v3/snapshot/options/{underlyingAsset}?expiration_date={ymd}
    url = f"https://api.polygon.io/v3/snapshot/options/{api_ticker}?expiration_date={expiry.isoformat()}&apiKey={api_key}&limit=250"
    
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching snapshot chain for {ticker} exp {expiry}...")
    
    all_results = []
    
    try:
        while url:
            resp = requests.get(url)
            if resp.status_code != 200:
                logger.error(f"Snapshot error {ticker}: {resp.status_code} {resp.text}")
                break
                
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            
            # Handle Pagination
            url = data.get("next_url")
            if url:
                url = f"{url}&apiKey={api_key}"
                time.sleep(0.05) # Brief pause for safety
                
    except Exception as e:
        logger.error(f"Error fetching snapshot: {e}")
        return pd.DataFrame()
        
    if not all_results:
        logger.warning(f"No contracts found for {ticker} exp {expiry} via snapshot.")
        return pd.DataFrame()
        
    # Process Results
    rows = []
    for r in all_results:
        details = r.get("details", {})
        day = r.get("day", {})
        greeks = r.get("greeks", {})
        
        contract_ticker = details.get("ticker")
        strike = details.get("strike_price")
        c_type = details.get("contract_type") # 'call' or 'put'
        
        # We need a price (Mid or Close).
        # Snapshot 'day' has OHLCV for the session. 'close' is the EOD close.
        # This is exactly what we want for "Previous Close" style calc if running pre-market.
        price = day.get("close")
        
        # Fallback to last_quote if day close is missing (illiquid?)
        # But 'day.close' is best for EOD markings.
        if price is None:
             # Try 'prev_day' if field exists? No, snapshot structure is specific.
             # If day data is missing, it didn't trade today.
             # We could fallback to 'previous_close' from details if available? No.
             # Just skip illiquid untraded contracts?
             # Actually, if we are recalculating Expected Moves based on "yesterday", we want yesterday's close.
             # If we run at 8am, "day" refers to PREV session (Polygon snapshots roll over?). 
             # Wait, Snapshot is "Real-time" usually. 
             # At 8AM, market is closed. "Day" OHLC usually resets at 9:30 or holds prev day?
             # Polygon docs: "Snapshot returns the most recent data."
             # If before open, it likely holds prev day.
             # Let's use 'close'. If None, skip.
             continue
             
        if not strike or not c_type:
            continue
            
        # Spot filter (efficiency) - filter broadly around spot if provided
        if spot_price:
            if abs(strike - spot_price) / spot_price > 0.30: # 30% wide net
                continue

        otype = 'C' if c_type == 'call' else ('P' if c_type == 'put' else None)
        
        rows.append({
            "strike": float(strike),
            "option_type": otype,
            "prev_close_mid": float(price),
            "iv": greeks.get("implied_volatility"), # Bonus: Snapshot gives IV!
            "gamma": greeks.get("gamma"),
            "oi": r.get("open_interest"),
            "contractSymbol": contract_ticker
        })
        
    df = pd.DataFrame(rows)
    return df
