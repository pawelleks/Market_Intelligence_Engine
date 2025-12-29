
import yfinance as yf
import pandas as pd

ticker = "SPY"
yf_ticker = yf.Ticker(ticker)
expirations = yf_ticker.options

# Find a far out expiration
target = [e for e in expirations if e.startswith('2026-06')]
if target:
    exp = target[0]
    print(f"Checking {exp}...")
    chain = yf_ticker.option_chain(exp)
    calls = chain.calls
    print(calls[['strike', 'lastPrice', 'openInterest']].head())
    print(f"Total OIs > 0: {(calls['openInterest'] > 0).sum()}")
else:
    print("No 2026-06 expiration found.")
