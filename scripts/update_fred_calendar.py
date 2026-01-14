import os
import json
import time
import httpx
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("fred_calendar")

# Config
FRED_API_KEY = os.getenv("FRED_API_KEY")
DATA_DIR = Path("data/calendar")
OUTPUT_FILE = "data/calendar/fred_release_calendar.json"
MAPPINGS_FILE = "config/tier2_release_mappings.json"

def load_series_list():
    """Extract all unique series IDs from the tier2 mappings."""
    if not Path(MAPPINGS_FILE).exists():
        LOG.error(f"Mappings file not found: {MAPPINGS_FILE}")
        return []
    
    with open(MAPPINGS_FILE, "r") as f:
        mappings = json.load(f)
        
    series_set = set()
    for config in mappings.values():
        for s in config.get("primary_series", []):
            series_set.add(s)
        for s in config.get("related_series", []):
            series_set.add(s)
            
    return list(series_set)

def fetch_series_release_id(client, series_id):
    """Get the release ID for a given series."""
    url = "https://api.stlouisfed.org/fred/series"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json"
    }
    
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        ser = data.get("seriess", [{}])[0]
        # FRED API doc says 'series', response provides 'seriess' array
        # This endpoint returns series metadata
        # Wait, series metadata usually doesn't include release_id directly?
        # Let's check: /fred/series/release endpoint is better.
        return None 
    except Exception as e:
        LOG.error(f"Error fetching metadata for {series_id}: {e}")
        return None

def fetch_release_for_series(client, series_id):
    """Get the release metadata (ID and Name) for a series."""
    url = "https://api.stlouisfed.org/fred/series/release"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json"
    }
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        releases = data.get("releases", [])
        if not releases:
            return None
        return releases[0] # Usually one release per series
    except Exception as e:
        LOG.error(f"Error fetching release for {series_id}: {e}")
        return None

def fetch_release_dates(client, release_id, min_date):
    """Fetch future release dates for a release ID."""
    url = "https://api.stlouisfed.org/fred/release/dates"
    params = {
        "release_id": release_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "realtime_start": min_date,
        "include_release_dates_with_no_data": "true"
    }
    # To get future dates, we filter the results. FRED returns past/future.
    # using realtime_start might not filter the release_date itself.
    # It filters when the info was known.
    
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("release_dates", [])
    except Exception as e:
        LOG.error(f"Error fetching dates for release {release_id}: {e}")
        return []

def main():
    if not FRED_API_KEY:
        LOG.error("FRED_API_KEY not set.")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    series_list = load_series_list()
    LOG.info(f"Loaded {len(series_list)} unique series IDs.")
    
    releases_map = defaultdict(list) # release_id -> list of series_ids
    release_info = {} # release_id -> {id, name, link}

    with httpx.Client(timeout=10.0) as client:
        # 1. Map Series -> Release ID
        for series_id in series_list:
            rel = fetch_release_for_series(client, series_id)
            if rel:
                rid = rel['id']
                releases_map[rid].append(series_id)
                release_info[rid] = rel
                LOG.info(f"Mapped {series_id} -> Release {rid} ({rel['name']})")
            else:
                LOG.warning(f"No release found for {series_id}")
            time.sleep(0.2) # Rate limit

        # 2. Fetch Dates for each Release
        today_str = datetime.now().strftime('%Y-%m-%d')
        lookahead = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        
        calendar_events = []
        
        for rid, series_ids in releases_map.items():
            r_meta = release_info[rid]
            dates = fetch_release_dates(client, rid, today_str)
            
            count = 0
            for d in dates:
                r_date = d.get('date')
                if r_date >= today_str:
                    event = {
                        'release_id': rid,
                        'release_name': r_meta['name'],
                        'release_date': r_date,
                        'release_time': '08:30', # FRED API doesn't always provide time in /release/dates? 
                                                # It is just date. Defaults to 08:30 ET for most.
                                                # Actually, some releases are different.
                        # But FRED /release/dates often has no time.
                        # We will default to 08:30 implies ET unless we know better.
                        'series_ids': series_ids
                    }
                    calendar_events.append(event)
                    count += 1
            
            LOG.info(f"Release {rid}: Found {count} upcoming dates.")
            time.sleep(0.2) 

        # Sort by date
        calendar_events.sort(key=lambda x: x['release_date'])
        
        # Save
        with open(OUTPUT_FILE, "w") as f:
            json.dump(calendar_events, f, indent=2)
            
        LOG.info(f"Saved {len(calendar_events)} events to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
