
import yfinance as yf
import pandas as pd
from datetime import date

def check_qqq():
    ticker = "QQQ"
    print(f"--- Checking {ticker} ---")
    
    # 1. Fetch Spot
    yf_t = yf.Ticker(ticker)
    try:
        fast_price = yf_t.fast_info['last_price']
        print(f"Fast Info Price: {fast_price}")
    except Exception as e:
        print(f"Fast Info Failed: {e}")
        
    try:
        hist = yf_t.history(period="1d")
        if not hist.empty:
            print(f"History Close: {hist['Close'].iloc[-1]}")
            print(f"History Date: {hist.index[-1]}")
        else:
            print("History Empty")
    except Exception as e:
        print(f"History Failed: {e}")

    # 2. Check CSV
    csv_path = f"data/raw/massive/options/options_2025-12-05.csv"
    try:
        df = pd.read_csv(csv_path)
        qqq_df = df[df['underlying_ticker'] == 'QQQ']
        if not qqq_df.empty:
            print(f"CSV Row Count for QQQ: {len(qqq_df)}")
            # Infer implied spot from ATM strikes (lowest gamma? no, strike distribution)
            # Just show min/max strike
            # Need to parse strike from osi if not present? 
            # My population script DID NOT save 'strike' column explicitly, it saved 'option_ticker'.
            # Wait, MassiveOptionsLoader parses it.
            # But the raw csv might not have it.
            # Let's peek at a few option tickers
            print("Sample Option Tickers:")
            print(qqq_df['option_ticker'].head(3).tolist())
    except Exception as e:
        print(f"CSV Check Failed: {e}")

if __name__ == "__main__":
    check_qqq()
