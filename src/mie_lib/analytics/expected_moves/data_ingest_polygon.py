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
from typing import Optional, Tuple, Any, List

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

def fetch_option_chain(
    ticker: str, 
    expiry: date, 
    as_of: date,
    provider: Any = None,
    spot_price: Optional[float] = None
) -> pd.DataFrame:
    """
    Fetches the option chain for a specific ticker and expiration date using Polygon Reference + Previous Close.
    Uses 'spot_price' to filter strikes (fetching only relevant ATM contracts).
    Returns a DataFrame with columns: ['strike', 'option_type', 'prev_close_mid', 'iv', 'contractSymbol']
    """
    api_key = _get_api_key()
    
    # Handle indices: ^SPX -> I:SPX
    api_ticker = ticker
    if ticker.startswith("^"):
        api_ticker = "I:" + ticker.replace("^", "")
    
    if spot_price is None:
        LOG.warning(f"No spot price provided for {ticker}, cannot filter contracts efficiently. Returning empty.")
        return pd.DataFrame()

    # 1. List Contracts from Reference API (Filtered)
    # Filter 10% around spot
    min_strike = spot_price * 0.90
    max_strike = spot_price * 1.10
    
    contracts_url = (
        f"https://api.polygon.io/v3/reference/options/contracts?"
        f"underlying_ticker={api_ticker}&"
        f"expiration_date={expiry.isoformat()}&"
        f"strike_price.gte={min_strike}&"
        f"strike_price.lte={max_strike}&"
        f"limit=100&" # Should strictly cover ATM
        f"apiKey={api_key}"
    )
    
    contract_results = []
    
    try:
        LOG.info(f"Listing contracts for {ticker} exp {expiry} around {spot_price}...")
        while contracts_url:
            resp = requests.get(contracts_url)
            if resp.status_code != 200:
                LOG.error(f"Contracts list error: {resp.status_code} {resp.text}")
                break
            
            data = resp.json()
            results = data.get("results", [])
            contract_results.extend(results)
            
            contracts_url = data.get("next_url")
            if contracts_url:
                contracts_url = f"{contracts_url}&apiKey={api_key}"
                time.sleep(0.05)
                
            # Safety break if too many
            if len(contract_results) > 200:
                break
                
    except Exception as e:
        LOG.error(f"Error listing contracts: {e}")
        return pd.DataFrame()
        
    if not contract_results:
        LOG.warning("No contracts found in strike range.")
        return pd.DataFrame()
        
    LOG.info(f"Found {len(contract_results)} contracts. Fetching previous close for each...")
    
    # 2. Fetch Previous Close for each contract
    processed_rows = []
    
    for c in contract_results:
        contract_ticker = c.get("ticker")
        strike = c.get("strike_price")
        c_type = c.get("contract_type")
        
        if not contract_ticker: continue
        
        # Get Prev Close
        # /v2/aggs/ticker/{ticker}/prev
        prev_url = f"https://api.polygon.io/v2/aggs/ticker/{contract_ticker}/prev?adjusted=true&apiKey={api_key}"
        
        try:
            # We must be careful with rate limits (5 calls/min usually for free, unlimited for paid)
            # User likely has paid since they have options/Polygon key? 
            # But earlier 403 on VIX implies weird plan status.
            # Assuming sufficient rate limit or will sleep.
            time.sleep(0.02) # minimal throttle
            
            p_resp = requests.get(prev_url)
            if p_resp.status_code == 200:
                p_data = p_resp.json()
                p_res = p_data.get("results", [])
                if p_res:
                    # Previous Close 'c'
                    price = p_res[0].get("c")
                    
                    if price is not None:
                         otype = 'C' if c_type == 'call' else ('P' if c_type == 'put' else None)
                         
                         processed_rows.append({
                            "strike": float(strike),
                            "option_type": otype,
                            "prev_close_mid": float(price), # Using Prev Close
                            "iv": None, # Cannot get IV from /prev easily
                            "contractSymbol": contract_ticker
                         })
            else:
                # 404 or 403
                # LOG.debug(f"Failed prev for {contract_ticker}: {p_resp.status_code}")
                pass
                
        except Exception:
            pass
            
    df = pd.DataFrame(processed_rows)
    return df
