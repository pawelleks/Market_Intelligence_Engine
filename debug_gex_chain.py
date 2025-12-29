
import yfinance as yf
import pandas as pd

ticker = "SPY"
yf_ticker = yf.Ticker(ticker)

# Force refresh?
expirations = yf_ticker.options
first_expiry = expirations[0]
print(f"Fetching chain for {first_expiry}...")

chain = yf_ticker.option_chain(first_expiry)
calls = chain.calls

print(f"Calls shape: {calls.shape}")
if not calls.empty:
    print(calls[['strike', 'lastPrice', 'bid', 'ask', 'items_VI', 'impliedVolatility', 'openInterest']].head())
    
    # Check nulls
    print("Null IVs:", calls['impliedVolatility'].isna().sum())
    print("Zero IVs:", (calls['impliedVolatility'] <= 0).sum())
    print("Null OIs:", calls['openInterest'].isna().sum())
    
    # Check column names just in case
    print("Columns:", calls.columns.tolist())
    
else:
    print("Calls are empty!")
