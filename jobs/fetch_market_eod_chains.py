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


def fetch_bulk_snapshot_oi(root: str, exp: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch bulk open interest snapshot for a root via ThetaData REST API.
    """
    url = f"{THETA_TERMINAL_URL}/v2/bulk_snapshot/option/open_interest?root={root}&exp={exp}"
    LOG.info(f"  Requesting bulk OI snapshot: {url}")
    
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                LOG.error(f"  Failed: HTTP {response.status}")
                return []
            data = json.loads(response.read())
    except Exception as e:
        LOG.error(f"  Error fetching bulk OI data: {e}")
        return []

    header_fmt = data.get("header", {}).get("format", [])
    if not header_fmt or "open_interest" not in header_fmt:
        return []
        
    idx_oi = header_fmt.index("open_interest")
    parsed_rows = []
    
    for item in data.get("response", []):
        contract = item.get("contract", {})
        ticks = item.get("ticks", [])
        if not contract or not ticks: continue
            
        exp_int = contract.get("expiration")
        strike_fixed = contract.get("strike", 0)
        right = contract.get("right")
        
        if not exp_int or not right: continue
        exp_str = str(exp_int)
        expiration = f"{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:]}" if len(exp_str) == 8 else exp_str
        strike = strike_fixed / 1000.0
        
        oi = ticks[-1][idx_oi]
        parsed_rows.append({
            "root": root, "expiration": expiration, "strike": strike, "right": right,
            "open_interest": oi
        })
    return parsed_rows


def fetch_bulk_eod(root: str, target_date: date) -> List[Dict[str, Any]]:
    """
    Fetch bulk EOD data (Volume, OHLC, Quote) for a root via ThetaData REST API.
    """
    fmt_date = target_date.strftime("%Y%m%d")
    url = f"{THETA_TERMINAL_URL}/v2/bulk_hist/option/eod?root={root}&exp=0&start_date={fmt_date}&end_date={fmt_date}"
    LOG.info(f"  Requesting bulk EOD hist: {url}")
    
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                LOG.error(f"  Failed: HTTP {response.status}")
                return []
            data = json.loads(response.read())
    except Exception as e:
        LOG.error(f"  Error fetching bulk EOD data: {e}")
        return []

    header_fmt = data.get("header", {}).get("format", [])
    if not header_fmt: return []
        
    try:
        idx_bid = header_fmt.index("bid")
        idx_ask = header_fmt.index("ask")
        idx_vol = header_fmt.index("volume")
        idx_close = header_fmt.index("close")
    except ValueError:
        LOG.error(f"  Required columns missing in header: {header_fmt}")
        return []
    
    parsed_rows = []
    for item in data.get("response", []):
        contract = item.get("contract", {})
        ticks = item.get("ticks", [])
        if not contract or not ticks: continue
            
        exp_int = contract.get("expiration")
        strike_fixed = contract.get("strike", 0)
        right = contract.get("right")
        
        if not exp_int or not right: continue
        exp_str = str(exp_int)
        expiration = f"{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:]}" if len(exp_str) == 8 else exp_str
        strike = strike_fixed / 1000.0
        
        latest_tick = ticks[-1]
        parsed_rows.append({
            "root": root, "expiration": expiration, "strike": strike, "right": right,
            "bid": latest_tick[idx_bid],
            "ask": latest_tick[idx_ask],
            "close": latest_tick[idx_close],
            "volume": latest_tick[idx_vol]
        })
            
    LOG.info(f"  Parsed {len(parsed_rows)} EOD contracts for {root}")
    return parsed_rows


def process_dataframe(eod_data: List[Dict[str, Any]], oi_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Join EOD and OI data into a single DataFrame.
    """
    if not eod_data:
        return pd.DataFrame()
        
    df_eod = pd.DataFrame(eod_data)
    df_oi = pd.DataFrame(oi_data) if oi_data else pd.DataFrame(columns=["root", "expiration", "strike", "right", "open_interest"])
    
    # Merge on contract key
    if not df_oi.empty:
        df = pd.merge(df_eod, df_oi, on=["root", "expiration", "strike", "right"], how="left")
    else:
        df = df_eod
        df["open_interest"] = 0
    
    # Coerce numeric
    for col in ["bid", "ask", "close", "volume", "open_interest"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # Calculate mid_price robustly
    def calc_mid(row):
        bid = row.get("bid", 0)
        ask = row.get("ask", 0)
        close = row.get("close", 0)
        
        # If we have both quotes, use them
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        
        # If we have a closing trade price, it's often better than a zero bid or empty quote
        if close > 0:
            return close
            
        # Fallback to single quote if the other is zero
        if ask > 0:
            return ask * 0.98 # Conservative estimate below offer
        if bid > 0:
            return bid * 1.02 # Conservative estimate above bid
            
        return 0.0

    df["mid_price"] = df.apply(calc_mid, axis=1)
    
    return df


def fetch_symbol(symbol: str, target_date: date) -> bool:
    """
    Fetch and save option chains for a symbol (including all roots).
    """
    LOG.info(f"Processing {symbol}...")
    
    # Check if output exists
    filename = f"chain_{symbol}_{target_date.strftime('%Y-%m-%d')}.parquet"
    output_path = OUTPUT_DIR / filename
    
    # Force overwrite if we want to upgrade existing stale files
    # if output_path.exists():
    #     LOG.info(f"Output exists: {output_path}. Skipping.")
    #     return True
        
    roots = SYMBOL_ROOTS.get(symbol, [symbol])
    all_eod = []
    all_oi = []
    
    for root in roots:
        eod = fetch_bulk_eod(root, target_date)
        if eod: all_eod.extend(eod)
        
        oi = fetch_bulk_snapshot_oi(root, exp=0)
        if oi: all_oi.extend(oi)
            
    if all_eod:
        df = process_dataframe(all_eod, all_oi)
        
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
