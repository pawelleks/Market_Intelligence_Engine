
import pandas as pd
import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from mie_lib.analytics.llm_payload import generate_llm_payload, _calc_level_rel_to_price

def test_dist_calc():
    print("--- Testing Distance Calculation ---")
    close = 694.07
    put_wall = 680.00
    
    # New Logic: ((Level - Close) / Close) * 100
    pct, label = _calc_level_rel_to_price(put_wall, close)
    print(f"Close: {close}, Put Wall: {put_wall}")
    print(f"Result: pct={pct}, label='{label}'")
    
    # Expected: 2.03% below current price
    expected_direction = "below" # Put wall is below price
    if expected_direction in label:
        print("SUCCESS: Label correctly says 'below'.")
    else:
        print(f"FAILURE: Label says '{label}'")

def test_full_payload():
    print("\n--- Testing Full Payload ---")
    # Mock DataFrame
    df = pd.DataFrame([{
        "date": "2025-01-12",
        "close": 694.07,
        "high_52w": 700.00,
        "low_52w": 500.00,
        "sma_200": 600.00,
        "hmm_state": 2,
        "ret_1d": 0.01
    }])
    
    # Mock GEX Snapshot
    gex_snapshot = {
        "net_gex": 100000,
        "profile": [
            {"strike": 680, "total_put_gex": -1000, "total_call_gex": 10},
            {"strike": 700, "total_put_gex": -10, "total_call_gex": 1000}
        ]
    }
    
    # Mock Expected Moves
    expected_moves = {
        "tickers": {
            "SPY": {
                "expirations": {
                    "next": {"days_to_expiry": 0, "em_dollars": 2.56},
                    "week": {"days_to_expiry": 4, "em_dollars": 12.50}
                }
            }
        }
    }
    
    payload = generate_llm_payload(df, "SPY", expected_moves, gex_snapshot)
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    test_dist_calc()
    test_full_payload()
