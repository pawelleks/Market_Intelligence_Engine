from datetime import date
from mie_lib.analytics.expected_moves.data_ingest import get_target_expirations

def test_dates(ticker):
    today = date(2025, 12, 16) # Simulate today
    odte, weekly, monthly = get_target_expirations(today)
    print(f"Ticker assumption {ticker} (Using generic logic):")
    print(f"  ODTE: {odte}")
    print(f"  Weekly: {weekly}")
    print(f"  Monthly: {monthly}")

if __name__ == "__main__":
    test_dates("SPY")
    test_dates("LLY")
