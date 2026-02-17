
import yfinance as yf
import pandas as pd

ticker = "SPY"
yf_ticker = yf.Ticker(ticker)
expirations = yf_ticker.options

print(f"Checking first 3 expirations for valid OI/IV...")

for exp in expirations[:3]:
    print(f"--- {exp} ---")
    try:
        chain = yf_ticker.option_chain(exp)
        calls = chain.calls
        if calls.empty:
            print("  Calls empty.")
            continue
            
        valid_oi = calls[calls['openInterest'] > 0]
        print(f"  Total Calls: {len(calls)}")
        print(f"  Calls with OI > 0: {len(valid_oi)}")
        
        valid_iv = calls[calls['impliedVolatility'] > 0.001]
        print(f"  Calls with IV > 0.001: {len(valid_iv)}")
    except Exception as e:
        print(f"Error: {e}")
