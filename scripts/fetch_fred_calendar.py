#!/usr/bin/env python3
"""
Fetch FRED economic releases calendar and cache locally.
This script fetches scheduled data releases from FRED API and caches them
for fast access by the calendar page.

Usage:
    python scripts/fetch_fred_calendar.py [--months N]
"""

import os
import sys
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

FRED_API_KEY = os.getenv("FRED_API_KEY")
OUTPUT_PATH = Path("data/raw/macro/fred_calendar.parquet")

# Default release time for releases without specific times (8:30 AM ET)
DEFAULT_RELEASE_TIME = "08:30"


def fetch_releases_for_period(start_date: str, end_date: str) -> list:
    """
    Fetch releases from FRED API for a given date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        List of release dictionaries
    """
    url = "https://api.stlouisfed.org/fred/releases/dates"
    params = {
        "realtime_start": start_date,
        "realtime_end": end_date,
        "include_release_dates_with_no_data": "true",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "limit": 1000  # Max per request
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("release_dates", [])
        else:
            print(f"  ✗ Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return []


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Fetch FRED economic releases calendar")
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="Number of months to fetch (default: 3, including current month)"
    )
    args = parser.parse_args()
    
    if not FRED_API_KEY:
        print("ERROR: FRED_API_KEY environment variable not set")
        sys.exit(1)
    
    print("=" * 70)
    print("FRED Economic Releases Calendar Fetcher")
    print("=" * 70)
    
    # Calculate date range: current month + next N-1 months
    today = datetime.now()
    start_date = today.replace(day=1)  # First day of current month
    end_date = start_date + relativedelta(months=args.months) - timedelta(days=1)
    
    print(f"\nFetching releases from {start_date.date()} to {end_date.date()}")
    print(f"({args.months} months total)\n")
    
    all_releases = []
    
    # Fetch month by month to stay within API limits
    for month_offset in range(args.months):
        month_start = start_date + relativedelta(months=month_offset)
        month_end = month_start + relativedelta(months=1) - timedelta(days=1)
        
        month_label = month_start.strftime("%B %Y")
        print(f"[{month_offset + 1}/{args.months}] Fetching {month_label}...", end=" ")
        
        releases = fetch_releases_for_period(
            month_start.strftime("%Y-%m-%d"),
            month_end.strftime("%Y-%m-%d")
        )
        
        if releases:
            all_releases.extend(releases)
            print(f"✓ {len(releases)} releases")
        else:
            print("✗ No releases found")
    
    if not all_releases:
        print("\n✗ No releases fetched. Exiting.")
        sys.exit(1)
    
    # Convert to DataFrame and add release time
    print(f"\nProcessing {len(all_releases)} total releases...")
    df = pd.DataFrame(all_releases)
    
    # Add default release time (most economic data is released at 8:30 AM ET)
    df["release_time"] = DEFAULT_RELEASE_TIME
    
    # Rename columns for clarity
    df = df.rename(columns={
        "date": "release_date"
    })
    
    # Select only needed columns
    df = df[["release_id", "release_name", "release_date", "release_time"]]
    
    # Sort by date
    df = df.sort_values("release_date")
    
    # Remove duplicates
    df = df.drop_duplicates(subset=["release_id", "release_date"])
    
    # Save to parquet
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    
    print(f"\n✓ Saved {len(df)} unique releases to {OUTPUT_PATH}")
    print(f"  Date range: {df['release_date'].min()} to {df['release_date'].max()}")
    print(f"  Unique releases: {df['release_id'].nunique()}")
    print("\nTop 10 upcoming releases:")
    
    # Show next 10 releases
    upcoming = df[df["release_date"] >= today.strftime("%Y-%m-%d")].head(10)
    for _, row in upcoming.iterrows():
        print(f"  - {row['release_date']} {row['release_time']}: {row['release_name']}")
    
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
