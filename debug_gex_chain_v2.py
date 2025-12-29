
import yfinance as yf
import pandas as pd

ticker = "SPY"
yf_ticker = yf.Ticker(ticker)

expirations = yf_ticker.options
first_expiry = expirations[0]
print(f"Fetching chain for {first_expiry}...")

chain = yf_ticker.option_chain(first_expiry)
calls = chain.calls

if not calls.empty:
    print(calls[['strike', 'lastPrice', 'impliedVolatility', 'openInterest']].head())
    
    print("Null IVs:", calls['impliedVolatility'].isna().sum())
    print("Zero IVs:", (calls['impliedVolatility'] <= 0).sum())
    print("Null OIs:", calls['openInterest'].isna().sum())
    print("Zero OIs:", (calls['openInterest'] <= 0).sum())
else:
    print("Calls empty")
