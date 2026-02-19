
import httpx
import os
import datetime
from datetime import date

THETA_HOST = os.getenv("THETA_HOST", "theta_terminal")
THETA_PORT = int(os.getenv("THETA_REST_PORT", "25510"))
BASE_URL = f"http://{THETA_HOST}:{THETA_PORT}"

def test_spx_endpoints():
    print(f"Testing SPX endpoints at {BASE_URL}...")
    
    # 1. Test Snapshot (Current method - failing?)
    try:
        url = f"{BASE_URL}/v2/snapshot/index/quote"
        params = {"root": "SPX"}
        print(f"\n1. GET {url}")
        resp = httpx.get(url, params=params, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:200]}...")
    except Exception as e:
        print(f"Snapshot failed: {e}")

    # 2. Test Hist Price (Streamer method - working?)
    try:
        today = date.today().strftime("%Y%m%d")
        url = f"{BASE_URL}/v2/hist/index/price"
        params = {
            "root": "SPX",
            "start_date": today,
            "end_date": today,
            "ivl": "0"
        }
        print(f"\n2. GET {url} (params={params})")
        resp = httpx.get(url, params=params, timeout=5)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        header = data.get("header", {}).get("format", [])
        rows = data.get("response", [])
        print(f"Header: {header}")
        print(f"Rows count: {len(rows)}")
        if rows:
            print(f"Last row: {rows[-1]}")
    except Exception as e:
        print(f"Hist request failed: {e}")

if __name__ == "__main__":
    test_spx_endpoints()
