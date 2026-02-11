
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import os
from pathlib import Path

# Config
TARGET_DATE = "2025-12-05"
TICKERS = ["SPY", "QQQ", "IWM", "DIA", "^SPX"]
OUTPUT_DIR = Path("data/raw/massive/options")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / f"options_{TARGET_DATE}.csv"

def format_osi(ticker, expiry_str, otype, strike):
    # expiry: YYYY-MM-DD -> YYMMDD
    dt = datetime.strptime(expiry_str, "%Y-%m-%d")
    yymmdd = dt.strftime("%y%m%d")
    
    # type: 'call'->C, 'put'->P
    t_char = 'C' if otype == 'call' else 'P'
    
    # strike: 450.0 -> 00450000 (x1000, padded to 8 chars)
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    
    # Clean ticker (remove ^ for OSI usually, but internal consistency matters more)
    # yfinance uses symbols like SPY, but ^SPX might need handling.
    # Usually ^SPX options are SPX or SPXW.
    # Let's keep the underlying ticker base for the first part.
    root = ticker.replace("^", "")
    # SPX has quirks but for our internal parser, as long as it matches regex ([A-Z]+), it works.
    
    return f"{root}{yymmdd}{t_char}{strike_str}"

def main():
    print(f"Fetching options snapshot for {TICKERS}...")
    
    all_rows = []
    
    for ticker in TICKERS:
        print(f"Processing {ticker}...")
        try:
            yf_t = yf.Ticker(ticker)
            exps = yf_t.options
            
            if not exps:
                print(f"  No expirations for {ticker}")
                continue
                
            for exp in exps:
                # print(f"  Fetching {exp}...")
                try:
                    chain = yf_t.option_chain(exp)
                    
                    # Process Calls
                    for _, row in chain.calls.iterrows():
                        osi = format_osi(ticker, exp, 'call', row['strike'])
                        all_rows.append({
                            "day": TARGET_DATE,
                            "underlying_ticker": ticker,
                            "option_ticker": osi,
                            "open_interest": row.get('openInterest', 0) or 0,
                            "implied_volatility": row.get('impliedVolatility', 0) or 0,
                            "gamma": 0, # Engine will calc
                            "delta": 0,
                            # Helper cols (optional but good for debug)
                            # "strike": row['strike'],
                            # "type": "call",
                            # "expiration": exp
                        })
                        
                    # Process Puts
                    for _, row in chain.puts.iterrows():
                        osi = format_osi(ticker, exp, 'put', row['strike'])
                        all_rows.append({
                            "day": TARGET_DATE,
                            "underlying_ticker": ticker,
                            "option_ticker": osi,
                            "open_interest": row.get('openInterest', 0) or 0,
                            "implied_volatility": row.get('impliedVolatility', 0) or 0,
                            "gamma": 0,
                            "delta": 0,
                        })
                        
                except Exception as e:
                    print(f"  Error fetching {exp}: {e}")
                    
        except Exception as e:
            print(f"Failed to process {ticker}: {e}")
            
    df = pd.DataFrame(all_rows)
    print(f"Total contracts fetched: {len(df)}")
    
    if not df.empty:
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"Saved to {OUTPUT_FILE}")
    else:
        print("No data fetched.")

if __name__ == "__main__":
    main()
