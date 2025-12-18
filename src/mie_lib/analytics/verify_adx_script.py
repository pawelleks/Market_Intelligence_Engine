
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path.cwd()))

from mie_lib.analytics.adx_api import get_adx_report
import json

try:
    response = get_adx_report("SPY")
    content = json.loads(response.body)
    print("API Endpoint Verification Success!")
    print(f"Ticker: {content['ticker']}")
    print(f"Latest Status: {content['latest']}")
    print(f"History Length: {len(content['history'])}")
    if len(content['history']) > 0:
        print(f"Sample History Item: {content['history'][0]}")
except Exception as e:
    print(f"API Endpoint Verification Failed: {e}")
