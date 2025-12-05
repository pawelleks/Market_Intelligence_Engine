
import yfinance as yf
import pandas as pd
from datetime import datetime

msg = []

def log(s):
    msg.append(str(s))
    print(s)

try:
    ticker = "SPY"
    yf_ticker = yf.Ticker(ticker)
    
    # 1. Spot
    spot = 0
    try:
        spot = yf_ticker.fast_info['last_price']
        log(f"Spot: {spot}")
    except:
        hist = yf_ticker.history(period="1d")
        spot = hist['Close'].iloc[-1]
        log(f"Spot (hist): {spot}")

    if not spot:
        log("No spot price")
        exit()

    # 2. Expirations
    exps = yf_ticker.options
    if not exps:
        log("No expirations")
        exit()
        
    log(f"Expirations: {exps[:3]} ...")
    
    # 3. Check Monthly expiry (approx 30 days out)
    # Find expiry closest to 30 days
    from datetime import date, timedelta
    target = date.today() + timedelta(days=25)
    expiry = min(exps, key=lambda x: abs((datetime.strptime(x, "%Y-%m-%d").date() - target).days))
    
    log(f"Checking expiry: {expiry}")
    
    chain = yf_ticker.option_chain(expiry)
    calls = chain.calls
    
    log(f"Calls shape: {calls.shape}")
    
    # Filter for ATM (+/- 5%)
    lower = spot * 0.95
    upper = spot * 1.05
    
    atm_calls = calls[(calls['strike'] >= lower) & (calls['strike'] <= upper)]
    log(f"ATM Strikes ({lower:.1f} - {upper:.1f}): {len(atm_calls)}")
    
    if not atm_calls.empty:
        # Check Columns
        log(atm_calls[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility', 'openInterest']].head(10).to_string())
    else:
        log("NO ATM CALLS FOUND!")
        
except Exception as e:
    log(f"Error: {e}")
