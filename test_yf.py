import yfinance as yf
import pandas as pd
from datetime import date

ticker = "SPY"
spy = yf.Ticker(ticker)

print("Fetching Spot...")
try:
    hist = spy.history(period="1d", interval="1m")
    if not hist.empty:
        print(f"Spot: {hist.iloc[-1]['Close']}")
    else:
        print("Spot: No data")
except Exception as e:
    print(f"Spot Error: {e}")

print("Fetching Options...")
try:
    expirations = spy.options
    print(f"Expirations: {expirations[:3]}")
    if expirations:
        chain = spy.option_chain(expirations[0])
        print(f"Calls: {chain.calls.head()}")
except Exception as e:
    print(f"Options Error: {e}")
