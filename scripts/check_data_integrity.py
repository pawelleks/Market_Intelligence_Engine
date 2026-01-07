#!/usr/bin/env python3
"""
Data Integrity Checker

Scans the data directory and validates that critical analytics files exist 
and are up-to-date (stale check).

Usage:
    python3 scripts/check_data_integrity.py --tickers SPY QQQ IWM
    python3 scripts/check_data_integrity.py --all

"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Paths configuration
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
FEATURES_DIR = DATA_DIR / "features"
ANALYTICS_DIR = DATA_DIR / "analytics"

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def get_file_age(path: Path) -> float:
    """Returns age of file in hours."""
    if not path.exists():
        return -1
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    age_hours = (now - mtime).total_seconds() / 3600
    return age_hours

def check_file(path: Path, max_age_hours=26) -> str:
    """Returns a status string (OK, STALE, MISSING)."""
    if not path.exists():
        return f"{RED}MISSING{RESET}"
    
    age = get_file_age(path)
    if age > max_age_hours:
        return f"{YELLOW}STALE ({age:.1f}h){RESET}"
    
    return f"{GREEN}OK ({age:.1f}h){RESET}"

def validate_ticker(ticker: str):
    """Checks all artifacts for a single ticker."""
    ticker = ticker.upper()
    
    # 1. OHLC Data
    ohlc_path = RAW_DIR / "ohlc" / f"{ticker}.parquet"
    if not ohlc_path.exists():
        ohlc_path = RAW_DIR / f"{ticker}.parquet" # Fallback legacy
        
    ohlc_status = check_file(ohlc_path)
    
    # 2. Features
    feat_path = FEATURES_DIR / f"{ticker}.parquet"
    feat_status = check_file(feat_path)
    
    # 3. Expected Moves
    em_path = ANALYTICS_DIR / "options" / f"{ticker.lower()}_expected_moves.parquet"
    em_status = check_file(em_path)
    
    # 4. GEX
    gex_path = ANALYTICS_DIR / "gex" / f"{ticker}_gex.json"
    gex_status = check_file(gex_path)

    # 5. HMM (Check base dir)
    hmm_path = ANALYTICS_DIR / "hmm" / ticker
    hmm_status = f"{GREEN}FOUND{RESET}" if hmm_path.exists() and any(hmm_path.iterdir()) else f"{RED}MISSING{RESET}"

    # Print Row
    print(f"{ticker:<8} | {ohlc_status:<20} | {feat_status:<20} | {em_status:<20} | {gex_status:<20} | {hmm_status}")

def main():
    parser = argparse.ArgumentParser(description="MIE Data Integrity Checker")
    parser.add_argument("--tickers", nargs="+", help="List of tickers to check")
    parser.add_argument("--all", action="store_true", help="Check all tickers found in raw data")
    args = parser.parse_args()
    
    tickers = args.tickers or ["SPY"]
    
    if args.all:
        # Discover tickers from RAW_DIR
        paths = list((RAW_DIR / "ohlc").glob("*.parquet")) + list(RAW_DIR.glob("*.parquet"))
        tickers = sorted(list(set([p.stem.upper() for p in paths])))
        
    print(f"{'Ticker':<8} | {'OHLC':<20} | {'Features':<20} | {'Exp. Moves':<20} | {'GEX':<20} | {'HMM'}")
    print("-" * 110)
    
    for t in tickers:
        validate_ticker(t)
        
if __name__ == "__main__":
    main()
