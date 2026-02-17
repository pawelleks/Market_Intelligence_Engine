from datetime import date, timedelta
from mie_lib.analytics.gex.gex_engine import GEXEngine

def test_dates():
    engine = GEXEngine()
    
    # Test 1: Today = Dec 16, 2025
    today = date(2025, 12, 16)
    horizons = engine._get_horizon_targets(today)
    
    print(f"--- As of {today} ---")
    for k, v in horizons.items():
        print(f"{k}: {v} (Weekday: {v.weekday()})")

    # expected:
    # eow: Dec 19 (Fri)
    # eom: Dec 31
    # eoq: Dec 31
    # next5: Dec 21
    
if __name__ == "__main__":
    test_dates()
