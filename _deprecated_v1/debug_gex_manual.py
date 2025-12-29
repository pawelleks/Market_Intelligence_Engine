
import yfinance as yf
import pandas as pd
from datetime import datetime

ticker = "SPY"
print(f"Fetching data for {ticker}...")
yf_ticker = yf.Ticker(ticker)

try:
    spot = yf_ticker.fast_info['last_price']
    print(f"Spot: {spot}")
except:
    print("Could not get fast_info spot")

expirations = yf_ticker.options
print(f"Expirations found: {len(expirations)}")
if len(expirations) > 1:
    second_exp = expirations[1]
    print(f"Checking second expiration: {second_exp}")
    
    chain = yf_ticker.option_chain(second_exp)
    calls = chain.calls
    
    print("Call Chain Head (2nd exp):")
    print(calls[['strike', 'lastPrice', 'openInterest', 'impliedVolatility']].head())

    # Check ATM
    if spot:
        atm_calls = calls[(calls['strike'] > spot - 5) & (calls['strike'] < spot + 5)]
        print("\nATM Calls (2nd exp):")
        print(atm_calls[['strike', 'lastPrice', 'openInterest', 'impliedVolatility']])
else:
    print("Only one expiration found.")
