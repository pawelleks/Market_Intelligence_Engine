
from mie_lib.analytics.gex.gex_engine import GEXEngine
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)

def check_puts():
    engine = GEXEngine()
    ticker = "QQQ"
    spot = 686.0
    
    print(f"--- Running GEX Engine for {ticker} (Spot={spot}) ---")
    data = engine.fetch_and_calculate_gex(ticker, spot_override=spot)
    
    if not data or 'profile' not in data:
        print("ERROR: No data returned from engine.")
        return

    profile = data['profile']
    df = pd.DataFrame(profile)
    
    if df.empty:
        print("ERROR: Profile DF is empty.")
        return
        
    print(f"Total Strikes: {len(df)}")
    
    # Calculate Totals
    total_call_gex = df['total_net_gex'].apply(lambda x: x if x > 0 else 0).sum() # Rough approx if net is proxy? No, need columns
    # Actually the profile has separate columns
    
    w_calls = df['weekly_call_gex'].sum()
    w_puts = df['weekly_put_gex'].sum()
    
    m_calls = df['monthly_call_gex'].sum()
    m_puts = df['monthly_put_gex'].sum()
    
    print(f"Weekly Calls: {w_calls:,.2f}")
    print(f"Weekly Puts:  {w_puts:,.2f}")
    print(f"Monthly Calls: {m_calls:,.2f}")
    print("\n--- Inspecting Raw Data for NEAR-THE-MONEY Puts (650-700) ---")
    # We need to access the raw chain. GEXEngine doesn't expose it easily in 'fetch_and_calculate_gex' 
    # unless we modify it or just use yfinance directly here.
    import yfinance as yf
    
    yf_ticker = yf.Ticker(ticker)
    exps = yf_ticker.options
    if not exps:
        print("No expirations found via YF.")
        return
        
    print(f"First Expiry: {exps[0]}")
    chain = yf_ticker.option_chain(exps[0])
    puts = chain.puts
    
    # Filter for relevant strikes
    near_puts = puts[(puts['strike'] >= 650) & (puts['strike'] <= 700)]
    
    if near_puts.empty:
        print("No Puts found between 650-700 in first expiry.")
        print(f"Puts Range: {puts['strike'].min()} - {puts['strike'].max()}")
    else:
        print(near_puts[['strike', 'lastPrice', 'openInterest', 'impliedVolatility']].to_string())

if __name__ == "__main__":
    check_puts()
