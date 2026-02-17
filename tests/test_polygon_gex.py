
import os
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_polygon")

# Use env var if available, else hardcode temporary test key if safe (DO NOT commit hardcoded key)
# I will trust the environment has POLYGON_API_KEY as per data_ingest_polygon.py
# But I need to verify it.
api_key = os.environ.get("POLYGON_API_KEY")

def test_polygon_snapshot(ticker="SPY"):
    if not api_key:
        print("POLYGON_API_KEY not found in env.")
        return

    # Try to fetch Option Snapshot for SPY
    # Requires underlying asset
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?limit=5&apiKey={api_key}"
    
    print(f"Fetching from {url}...")
    try:
        resp = requests.get(url)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Found {len(results)} contracts in snapshot.")
            if results:
                sample = results[0]
                print("--- Sample Contract ---")
                details = sample.get("details", {})
                day = sample.get("day", {})
                greeks = sample.get("greeks", {})
                
                print(f"Ticker: {details.get('ticker')}")
                print(f"Strike: {details.get('strike_price')}")
                print(f"Expiry: {details.get('expiration_date')}")
                print(f"OI: {sample.get('open_interest')}") # Check if this field exists!
                print(f"IV: {greeks.get('implied_volatility')}")
                print(f"Delta: {greeks.get('delta')}")
                print(f"Gamma: {greeks.get('gamma')}")
        else:
            print(f"Error: {resp.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_polygon_snapshot()
