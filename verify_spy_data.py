
import yfinance as yf
from datetime import date, datetime
import pandas as pd

def check_spy():
    print(f"--- Checking SPY Data at {datetime.now()} ---")
    
    # 1. Spot Price
    ticker = yf.Ticker("SPY")
    close_price = None
    
    # Fetch recent history
    hist = ticker.history(period="5d", interval="1d")
    print("\nRecent Price History (Last 5 Days):")
    print(hist.tail())
    
    if not hist.empty:
        close_price = hist["Close"].iloc[-1]
        last_date = hist.index[-1]
        print(f"\nLatest Close: {close_price:.2f} on {last_date}")
        
    # 2. Options Data for Today/Next Expiry (0DTE)
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\nChecking Options for Today/Next: {today_str}")
    
    try:
        expirations = ticker.options
        if not expirations:
            print("No expirations found!")
            return

        print(f"Expirations found: {expirations[:3]}...")
        
        # Determine 0DTE (Today if available, else next)
        # Assuming today is trading day (Monday), we expect today in list if 0DTE exists
        target_exp = expirations[0]
        print(f"Using Expiry: {target_exp}")
        
        opts = ticker.option_chain(target_exp)
        calls = opts.calls
        puts = opts.puts
        
        # Calculate Expected Move (Implied Move) at ATM
        # EM = 0.85 * ATM Comb Price
        if close_price:
            atm_strike = round(close_price)
            print(f"ATM Strike approx: {atm_strike}")
            
            # Find ATM Call/Put
            # Simple nearest strike
            c_atm = calls.iloc[(calls['strike'] - atm_strike).abs().argsort()[:1]]
            p_atm = puts.iloc[(puts['strike'] - atm_strike).abs().argsort()[:1]]
            
            print("\nATM Call:")
            print(c_atm[['contractSymbol', 'lastTradeDate', 'strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility']].to_string())
            
            print("\nATM Put:")
            print(p_atm[['contractSymbol', 'lastTradeDate', 'strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility']].to_string())
            
            c_price = (c_atm['bid'].values[0] + c_atm['ask'].values[0]) / 2.0
            p_price = (p_atm['bid'].values[0] + p_atm['ask'].values[0]) / 2.0
            
            # Note: yfinance bid/ask can be 0 sometimes if market closed or delayed
            if c_price == 0: c_price = c_atm['lastPrice'].values[0]
            if p_price == 0: p_price = p_atm['lastPrice'].values[0]
            
            straddle = c_price + p_price
            em = 0.85 * straddle
            
            print(f"\nCalculated ATM Straddle Price: ${straddle:.2f}")
            print(f"Approx Expected Move: +/- ${em:.2f}")
            print(f"Range: {close_price - em:.2f} to {close_price + em:.2f}")

    except Exception as e:
        print(f"Error fetching options: {e}")

if __name__ == "__main__":
    check_spy()
