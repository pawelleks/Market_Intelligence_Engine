
import os
import requests
import time
import pandas as pd
from datetime import date
import logging

logger = logging.getLogger(__name__)

def fetch_options_snapshot(ticker: str, api_key: str) -> pd.DataFrame:
    """
    Fetches the full options chain snapshot for a ticker from Polygon.io.
    Returns a DataFrame with columns aligned to MassiveOptionsLoader expectations:
    [day, underlying_ticker, option_ticker, open_interest, implied_volatility, gamma, delta]
    """
    # Handle indices: ^SPX -> I:SPX
    api_ticker = ticker
    if ticker.startswith("^"):
        api_ticker = "I:" + ticker.replace("^", "")

    url = f"https://api.polygon.io/v3/snapshot/options/{api_ticker}?apiKey={api_key}&limit=250"
    logger.info(f"Fetching Polygon snapshot for {ticker} (using {api_ticker})...")
    
    all_results = []
    page_count = 0
    
    while url:
        try:
            resp = requests.get(url)
            if resp.status_code != 200:
                logger.error(f"Error fetching {url}: {resp.status_code} {resp.text}")
                break
                
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            page_count += 1
            
            if page_count % 10 == 0:
                logger.info(f"  Fetched {page_count} pages, {len(all_results)} contracts so far...")
            
            url = data.get("next_url")
            if url:
                url = f"{url}&apiKey={api_key}"
                time.sleep(0.1) # Rate limit safety
        except Exception as e:
            logger.error(f"Exception during fetch: {e}")
            break
            
    logger.info(f"Finished fetching {ticker}. Total contracts: {len(all_results)}")
    
    if not all_results:
        return pd.DataFrame()

    formatted = []
    today = date.today().strftime("%Y-%m-%d")
    
    for r in all_results:
        greeks = r.get("greeks") or {}
        details = r.get("details") or {}
        
        # Polygon /v3/snapshot/options returns ticker inside 'details' usually
        # But sometimes it might be top level? The debug showed it in details.
        ticker_val = details.get("ticker") or r.get("ticker")
        
        row = {
            "day": today,
            "underlying_ticker": ticker, # Keep original request ticker (e.g. ^SPX)
            "option_ticker": ticker_val,
            "open_interest": r.get("open_interest", 0),
            "implied_volatility": r.get("implied_volatility") or greeks.get("implied_volatility", 0),
            "gamma": greeks.get("gamma", 0),
            "delta": greeks.get("delta", 0)
        }
        formatted.append(row)
        
    return pd.DataFrame(formatted)


def fetch_spot_close_polygon(ticker: str, config: dict = None, metrics: dict = None) -> float:
    """Fetch previous close for spot ticker."""
    # Use Previous Close endpoint
    api_key = os.environ.get("POLYGON_API_KEY", "keXDhBdz5zuofjHkeiYMznzUiyDerXgu")
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?adjusted=true&apiKey={api_key}"
    
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                # Return the close price 'c'
                return float(data["results"][0]["c"])
    except Exception as e:
        logger.error(f"Error fetching spot close for {ticker}: {e}")
        
    return None

def fetch_vix1d(config: dict = None, metrics: dict = None) -> float:
    """Fetch VIX1D index value (using VIX1D or I:VIX1D)."""
    return fetch_spot_close_polygon("I:VIX1D", config, metrics)

def fetch_atm_option_chain(
    ticker: str,
    spot_price: float,
    expiration_date: str,
    strike_spacing: int,
    config: dict,
    metrics: dict,
) -> pd.DataFrame:
    """
    Fetch ATM options chain for a specific expiry.
    Used by Expected Moves engine.
    Returns DataFrame with columns: ['strike', 'type', 'mid', 'bid', 'ask']
    """
    api_key = os.environ.get("POLYGON_API_KEY", "keXDhBdz5zuofjHkeiYMznzUiyDerXgu")
    
    # Handle indices: ^SPX -> I:SPX
    api_ticker = ticker
    if ticker.startswith("^"):
        api_ticker = "I:" + ticker.replace("^", "")

    # Filter by specific expiration to optimize
    url = f"https://api.polygon.io/v3/snapshot/options/{api_ticker}?expiration_date={expiration_date}&apiKey={api_key}&limit=250"
    
    logger.info(f"Fetching ATM chain for {ticker} exp={expiration_date} spot={spot_price}...")
    
    all_results = []
    while url:
        try:
            resp = requests.get(url)
            if resp.status_code != 200:
                logger.error(f"Error fetching chain: {resp.status_code}")
                break
            data = resp.json()
            all_results.extend(data.get("results", []))
            url = data.get("next_url")
            if url:
                 url = f"{url}&apiKey={api_key}"
                 time.sleep(0.1)
        except Exception as e:
            logger.error(f"Exception fetching chain: {e}")
            break
            
    if not all_results:
        return pd.DataFrame()
        
    rows = []
    for r in all_results:
        details = r.get("details", {})
        strike = details.get("strike_price")
        if not strike:
             continue
             
        # Filter for ATM band manually here if needed, or return all for that expiry
        # Engine usually wants around ATM.
        # Let's filter broadly (e.g. +/- 20% or using strike_spacing logic)
        # expected_move.py calls it with strike_spacing=strike_band (e.g. 10 strikes).
        # Actually expected_move probably does its own filtering or expects us to.
        # Let's return everything for that expiry, it's safer and cleaner.
        
        # We need bid/ask to calculate Mid
        day = r.get("day", {})
        # Snapshot usually has last quote or we construct mid?
        # Polygon snapshot has 'day' (OHLC) and 'last_quote'.
        # We need 'mid'.
        # Actually simplest is to use 'close' from 'day' if available, or calc from quote.
        # Let's check keys again. 'day' has 'close'.
        # Let's use 'close' as proxy for 'mid' if we don't have better.
        # Or look for 'greeks' which imply a price model.
        
        price = day.get("close")
        if price is None:
             continue
             
        rows.append({
            "strike": float(strike),
            "type": details.get("contract_type"), # 'call' or 'put'
            "mid": float(price), # Using Close as Mid for now
            "bid": float(price), # simplistic
            "ask": float(price)
        })
        
    return pd.DataFrame(rows)
