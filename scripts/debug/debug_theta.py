import httpx
import sys

URL = "http://theta_terminal:25510/v2/hist/stock/eod"
PARAMS = {"root": "SPY", "start_date": "20260209", "end_date": "20260216"}

print(f"Connecting to {URL} with {PARAMS}...")
try:
    with httpx.Client() as client:
        resp = client.get(URL, params=PARAMS, timeout=10.0)
        print(f"Status Code: {resp.status_code}")
        print("Response Headers:", resp.headers)
        print("Response Body:", resp.text)
except Exception as e:
    print(f"Connection Failed: {e}")
