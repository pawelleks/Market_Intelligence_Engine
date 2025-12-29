
import pandas as pd
import sys
import logging
# Add src to path
sys.path.insert(0, "./src")

from mie_lib.analytics.gex.gex_engine import GEXEngine

def test_gex_invalid_dates():
    engine = GEXEngine()
    
    # Create mock dataframe with:
    # 1. Valid row
    # 2. Invalid row (None)
    # 3. Invalid row ('nan')
    # 4. Invalid row ('garbage')
    data = [
        {"strike": 100, "type": "call", "expiration": "2025-12-31", "oi": 100, "iv": 0.2, "gamma": 0.05},
        {"strike": 100, "type": "call", "expiration": None, "oi": 100, "iv": 0.2, "gamma": 0.05},
        {"strike": 100, "type": "call", "expiration": "nan", "oi": 100, "iv": 0.2, "gamma": 0.05},
        {"strike": 100, "type": "call", "expiration": "InvalidDate", "oi": 100, "iv": 0.2, "gamma": 0.05},
    ]
    df = pd.DataFrame(data)
    
    print("Testing GEX Engine with invalid dates...")
    try:
        # ticker='TEST', spot=100
        result = engine.calculate_gex_from_frame("TEST", df, 100.0)
        
        # Check if we got a result
        if not result:
            print("FAILED: No result returned.")
            sys.exit(1)
            
        print("SUCCESS: Engine did not crash.")
        print(f"Result keys: {result.keys()}")
        
        # We expect only the valid row to contribute.
        # Check profile or net_gex
        print(f"Net GEX: {result.get('net_gex')}")
        
    except Exception as e:
        print(f"FAILED: Engine crashed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_gex_invalid_dates()
