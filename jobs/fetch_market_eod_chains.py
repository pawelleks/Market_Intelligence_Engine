#!/usr/bin/env python3
"""
Market EOD Option Chain Fetcher (Bulk Version)

Fetches End-of-Day (EOD) full option chains for multiple symbols using ThetaData's Bulk Snapshot API.
significantly faster than iterating through strikes.

Output: data/raw/chain_[SYMBOL]_[YYYY-MM-DD].parquet
"""

import os
import sys
import json
import time
import logging
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
LOG = logging.getLogger("fetch_market_eod_chains")

# =============================================================================
# CONFIGURATION
# =============================================================================
TARGET_SYMBOLS = ['SPX', 'SPY', 'QQQ', 'IWM']

# Symbol-specific roots (some indices have weekly variants)
SYMBOL_ROOTS = {
    'SPX': ['SPX', 'SPXW'],      # SPX + Weeklies
    'SPY': ['SPY'],              # ETF
    'QQQ': ['QQQ'],              # ETF
    'IWM': ['IWM'],              # ETF
}

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"
THETA_TERMINAL_URL = "http://theta_terminal:25510"  # Internal docker network host

def get_target_date() -> date:
    """
    Determine the target date for EOD data.
    - If run after 16:30 EST: use today
    - If run before 16:30 EST: use yesterday
    - Skip weekends
    """
    from zoneinfo import ZoneInfo
    
    # Simple fallback if zoneinfo missing (though it's in 3.9+)
    try:
        now_est = datetime.now(ZoneInfo("America/New_York"))
    except:
        now_est = datetime.utcnow() - timedelta(hours=5) # Rough EST approximation

    market_close = now_est.replace(hour=16, minute=30, second=0, microsecond=0)
    
    if now_est >= market_close:
        target = now_est.date()
    else:
        target = (now_est - timedelta(days=1)).date()
    
    # Skip weekends
    while target.weekday() >= 5:  # Saturday=5, Sunday=6
        target -= timedelta(days=1)
    
    LOG.info(f"Target date for EOD data: {target}")
    return target


def fetch_bulk_snapshot(root: str, exp: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch bulk option snapshot for a root via ThetaData REST API.
    exp=0 means ALL expirations.
    """
    url = f"{THETA_TERMINAL_URL}/v2/bulk_snapshot/option/quote?root={root}&exp={exp}"
    LOG.info(f"  Requesting bulk snapshot: {url}")
    
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                LOG.error(f"  Failed: HTTP {response.status}")
                return []
            
            data = json.loads(response.read())
    except urllib.error.URLError as e:
        LOG.error(f"  Connection error: {e}")
        return []
    except Exception as e:
        LOG.error(f"  Error fetching bulk data: {e}")
        return []

    # Parse response
    # JSON structure:
    # {
    #   "header": { "format": ["ms_of_day", "bid_size", "bid_exchange", "bid", ... ] },
    #   "response": [
    #       { "contract": {...}, "ticks": [[...values...]] },
    #       ...
    #   ]
    # }
    
    header_fmt = data.get("header", {}).get("format", [])
    if not header_fmt:
        LOG.error("  No header format found in response")
        return []
        
    # Map column names to indices
    try:
        idx_bid = header_fmt.index("bid")
        idx_ask = header_fmt.index("ask")
    except ValueError:
        LOG.error(f"  Required columns 'bid'/'ask' not found in header: {header_fmt}")
        return []
    
    parsed_rows = []
    
    for item in data.get("response", []):
        contract = item.get("contract", {})
        ticks = item.get("ticks", [])
        
        if not contract or not ticks:
            continue
            
        # Extract contract details
        # expiration is usually YYYYMMDD as integer
        exp_int = contract.get("expiration")
        strike_fixed = contract.get("strike", 0)
        right = contract.get("right")
        
        if not exp_int or not right:
            continue

        # Convert date integer to string YYYY-MM-DD
        exp_str = str(exp_int)
        if len(exp_str) == 8:
            expiration = f"{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:]}"
        else:
            expiration = exp_str
            
        # Convert strike (fixed point implied 1000ths usually? e.g. 5375000 = 5375.000)
        # API docs say strike is in millicents? No, typically ThetaData v2 is 1/10th cent (1000 divisor)?
        # Let's assume standard divisor of 1000 for strikes > 10000 logic previously seen
        # wait, previous script: s / 1000 if s > 10000
        strike = strike_fixed / 1000.0
        
        # Get latest tick (last one in list?)
        # Snapshot typically implies one tick per contract, but 'ticks' is a list.
        # usually it's just one list inside ticks: [ [col1, col2...] ]
        if len(ticks) > 0:
            latest_tick = ticks[-1]
            
            bid = latest_tick[idx_bid]
            ask = latest_tick[idx_ask]
            
            parsed_rows.append({
                "root": root,
                "expiration": expiration,
                "strike": strike,
                "right": right,
                "bid": bid,
                "ask": ask
            })
            
    LOG.info(f"  Parsed {len(parsed_rows)} contracts for {root}")
    return parsed_rows


def process_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert list of dicts to DataFrame and calculate mid_price.
    """
    if not data:
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    
    # coerce numeric
    df["bid"] = pd.to_numeric(df["bid"], errors="coerce")
    df["ask"] = pd.to_numeric(df["ask"], errors="coerce")
    
    # Calculate mid_price
    df["mid_price"] = (df["bid"] + df["ask"]) / 2.0
    
    # Fill NaN mid_price with 0 or drop? 
    # Usually better to keep but can filter out zero-bids if needed
    # Previous script extracted 'close' if bid/ask missing. Here we only asked for Quote.
    
    return df


def fetch_symbol(symbol: str, target_date: date) -> bool:
    """
    Fetch and save option chains for a symbol (including all roots).
    """
    LOG.info(f"Processing {symbol}...")
    
    # Check if output exists
    filename = f"chain_{symbol}_{target_date.strftime('%Y-%m-%d')}.parquet"
    output_path = OUTPUT_DIR / filename
    
    if output_path.exists():
        # Optional: Check if file is small/empty?
        # For now, skip if exists to avoid overwriting good data
        LOG.info(f"Output exists: {output_path}. Skipping.")
        return True
        
    roots = SYMBOL_ROOTS.get(symbol, [symbol])
    all_data = []
    
    for root in roots:
        data = fetch_bulk_snapshot(root, exp=0) # 0 = All expirations
        if data:
            all_data.extend(data)
            
    if all_data:
        df = process_dataframe(all_data)
        
        # Ensure directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        df.to_parquet(output_path, index=False)
        LOG.info(f"Saved {symbol} chain to {output_path} ({len(df)} rows)")
        return True
    else:
        LOG.warning(f"No data found for {symbol}")
        return False


def main():
    LOG.info("=" * 60)
    LOG.info("Starting Market EOD Chains Fetch Job (Bulk V2)")
    LOG.info(f"Symbols: {TARGET_SYMBOLS}")
    LOG.info("=" * 60)
    
    target_date = get_target_date()
    # Wait for thetadata terminal? It's usually up.
    
    results = {}
    
    for symbol in TARGET_SYMBOLS:
        try:
            success = fetch_symbol(symbol, target_date)
            results[symbol] = "SUCCESS" if success else "EMPTY"
        except Exception as e:
            LOG.error(f"Failed to process {symbol}: {e}")
            results[symbol] = f"FAILED: {e}"
            
    # Summary
    LOG.info("-" * 60)
    LOG.info("Job Summary:")
    success_count = 0
    for sym, status in results.items():
        LOG.info(f"  {sym}: {status}")
        if status == "SUCCESS":
            success_count += 1
            
    if success_count > 0:
        LOG.info(f"Job COMPLETED: {success_count}/{len(TARGET_SYMBOLS)} symbols")
        return 0
    else:
        LOG.error("Job FAILED: No symbols processed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
