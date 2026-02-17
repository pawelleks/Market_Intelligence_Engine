#!/usr/bin/env python3
"""
Test FRED releases/dates API endpoint to verify calendar data availability.
"""
import os
import sys
import requests
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load API key from environment
FRED_API_KEY = os.getenv("FRED_API_KEY")

if not FRED_API_KEY:
    print("ERROR: FRED_API_KEY not found in environment")
    sys.exit(1)

# Test the releases/dates endpoint
url = "https://api.stlouisfed.org/fred/releases/dates"
params = {
    "realtime_start": "2026-01-01",
    "realtime_end": "2026-01-31",
    "include_release_dates_with_no_data": "true",
    "api_key": FRED_API_KEY,
    "file_type": "json"
}

print("Testing FRED releases/dates API...")
print(f"URL: {url}")
print(f"Date range: {params['realtime_start']} to {params['realtime_end']}")
print()

try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Success! Found {len(data.get('release_dates', []))} scheduled releases")
        print("\nSample releases:")
        for release in data.get('release_dates', [])[:10]:
            print(f"  - {release['date']}: {release['release_name']} (ID: {release['release_id']})")
    else:
        print(f"\n✗ Error: {response.text}")
        
except Exception as e:
    print(f"\n✗ Exception: {e}")
