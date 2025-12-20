
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

try:
    from mie_lib.analytics.gex.api_endpoints import get_latest_gex, _GEX_CACHE
    from mie_lib.analytics.gex.storage import load_gex_profile
    
    ticker = "SPY"
    print(f"Testing GEX API logic for {ticker}...")
    
    # 1. Test direct storage load
    print("1. Testing load_gex_profile...")
    data = load_gex_profile(ticker)
    if data:
        print("   [scan] Found data on disk.")
        print(f"   Timestamp: {data.get('timestamp')}")
    else:
        print("   [scan] No data found on disk.")

    # 2. Test API function (mocking request)
    print("\n2. Testing get_latest_gex function...")
    try:
        result = get_latest_gex(ticker)
        print("   [success] API returned data.")
        print(f"   Keys: {list(result.keys())}")
        print(f"   Net GEX: {result.get('net_gex')}")
    except Exception as e:
        print(f"   [error] API failed: {e}")

except ImportError as e:
    print(f"Import Error: {e}")
    # Print sys.path to debug
    print(sys.path)
except Exception as e:
    print(f"General Error: {e}")
