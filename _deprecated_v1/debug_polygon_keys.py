
import os
import requests
import json

# API Key fallback
API_KEY = os.environ.get("POLYGON_API_KEY", "keXDhBdz5zuofjHkeiYMznzUiyDerXgu")

def debug_keys():
    url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={API_KEY}&limit=1"
    print(f"Fetching {url}")
    try:
        resp = requests.get(url)
        data = resp.json()
        results = data.get("results", [])
        if results:
            print("First result keys:", list(results[0].keys()))
            print("First result content:", json.dumps(results[0], indent=2))
        else:
            print("No results found.")
    except Exception as e:
        print(e)
        
debug_keys()
