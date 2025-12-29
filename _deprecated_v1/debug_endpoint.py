from mie_lib.analytics.expected_moves.api_endpoints import get_reliability_history
import pandas as pd
import logging

# Setup logging to see errors
logging.basicConfig(level=logging.INFO)

try:
    print("Calling get_reliability_history(ticker='SPY')...")
    result = get_reliability_history(ticker="SPY")
    print(f"Result type: {type(result)}")
    if isinstance(result, list):
        print(f"Result count: {len(result)}")
        if len(result) > 0:
            print("First record:", result[0])
    else:
        print("Result:", result)
except Exception as e:
    print("Caught exception:")
    print(e)
    import traceback
    traceback.print_exc()
