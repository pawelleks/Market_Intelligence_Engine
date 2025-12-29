import yfinance as yf
import pandas as pd

def verify_yf_data(ticker_symbol="SPY"):
    print(f"Fetching data for {ticker_symbol}...")
    ticker = yf.Ticker(ticker_symbol)
    
    # Get expiration dates
    expirations = ticker.options
    if not expirations:
        print("No expirations found.")
        return

    # Pick the first expiration
    first_expiry = expirations[0]
    print(f"Checking Expiration: {first_expiry}")
    
    # Fetch chain
    chain = ticker.option_chain(first_expiry)
    calls = chain.calls
    
    if calls.empty:
        print("No calls found.")
        return

    print(f"\n--- Columns Available ({len(calls.columns)}) ---")
    print(list(calls.columns))
    
    print("\n--- Sample Row ---")
    print(calls.iloc[0].to_dict())
    
    # Check specifically for Open Interest and IV
    has_oi = 'openInterest' in calls.columns
    has_iv = 'impliedVolatility' in calls.columns
    has_vega = 'vega' in calls.columns # Unlikely, but checking
    has_delta = 'delta' in calls.columns # Unlikely

    print("\n--- Data Check ---")
    print(f"Has Open Interest: {has_oi}")
    print(f"Has Implied Volatility: {has_iv}")
    print(f"Has Delta/Gamma/Vega: {has_delta} / {has_vega}")

if __name__ == "__main__":
    verify_yf_data()
