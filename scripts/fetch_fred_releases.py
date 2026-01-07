#!/usr/bin/env python3
"""
Bulk fetch FRED release information for all series in macro_series.yml
and cache in parquet format for fast access.

Usage:
    python scripts/fetch_fred_releases.py
"""

import os
import sys
import yaml
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

FRED_API_KEY = os.getenv("FRED_API_KEY")
CONFIG_PATH = Path("config/macro_series.yml")
OUTPUT_PATH = Path("data/raw/macro/fred_releases.parquet")

def load_series_ids() -> List[str]:
    """Load all FRED series IDs from configuration."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    
    return list(config.get("series", {}).keys())

def estimate_next_release(last_date: str, frequency: str) -> str:
    """
    Estimate next release date based on frequency and last data date.
    Ensures the returned date is always in the future.
    Note: This is an estimation since FRED doesn't provide future release calendars via API.
    """
    try:
        last_dt = datetime.strptime(last_date, "%Y-%m-%d")
    except:
        return None
    
    # Frequency mappings to approximate days
    freq_map = {
        "D": 1,      # Daily
        "W": 7,      # Weekly
        "BW": 14,    # Biweekly
        "M": 30,     # Monthly
        "Q": 90,     # Quarterly
        "SA": 180,   # Semiannual
        "A": 365,    # Annual
    }
    
    days_ahead = freq_map.get(frequency, 30)  # Default to monthly
    next_date = last_dt + timedelta(days=days_ahead)
    
    # Keep advancing until we get a future date
    today = datetime.now()
    while next_date <= today:
        next_date += timedelta(days=days_ahead)
    
    return next_date.strftime("%Y-%m-%d")

def fetch_series_info(series_id: str) -> Dict:
    """Fetch series metadata from FRED API."""
    url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "seriess" in data and len(data["seriess"]) > 0:
                return data["seriess"][0]
    except Exception as e:
        print(f"Error fetching {series_id}: {e}")
    
    return None

def fetch_series_observations(series_id: str) -> str:
    """Get the last observation date for a series."""
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "observations" in data and len(data["observations"]) > 0:
                return data["observations"][0]["date"]
    except Exception as e:
        print(f"Error fetching observations for {series_id}: {e}")
    
    return None

def fetch_series_release_id(series_id: str) -> Optional[int]:
    """Fetch release ID for a series from FRED API."""
    url = f"https://api.stlouisfed.org/fred/series/release?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "releases" in data and len(data["releases"]) > 0:
                return data["releases"][0]["id"]
    except Exception as e:
        print(f"Error fetching release for {series_id}: {e}")
    
    return None

def main():
    """Main execution function."""
    if not FRED_API_KEY:
        print("ERROR: FRED_API_KEY environment variable not set")
        sys.exit(1)
    
    print("Loading series IDs from configuration...")
    series_ids = load_series_ids()
    print(f"Found {len(series_ids)} series to fetch")
    
    results = []
    
    for i, series_id in enumerate(series_ids, 1):
        print(f"[{i}/{len(series_ids)}] Fetching {series_id}...", end=" ")
        
        # Get series metadata
        info = fetch_series_info(series_id)
        if not info:
            print("SKIP (no metadata)")
            continue
        
        # Get last observation date
        last_date = fetch_series_observations(series_id)
        if not last_date:
            print("SKIP (no observations)")
            continue
            
        # Get release ID
        release_id = fetch_series_release_id(series_id)
        
        frequency = info.get("frequency_short", "M")
        title = info.get("title", "")
        
        # Estimate next release
        next_release = estimate_next_release(last_date, frequency)
        
        results.append({
            "series_id": series_id,
            "release_name": title,
            "release_id": release_id,
            "frequency": frequency,
            "last_observation": last_date,
            "release_date": next_release,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        print(f"OK (next: {next_release}, release_id: {release_id})")
    
    # Save to parquet
    if results:
        df = pd.DataFrame(results)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(OUTPUT_PATH, index=False)
        print(f"\n✓ Saved {len(results)} release records to {OUTPUT_PATH}")
    else:
        print("\n✗ No data fetched")

if __name__ == "__main__":
    main()
