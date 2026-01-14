
import os
import glob
import pandas as pd
import re
from datetime import datetime
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from mie_lib.analytics.gex.gex_engine import GEXEngine

DATA_DIR = "data/raw/massive/options"
HISTORY_DIR = "data/analytics/gex/history"
TICKER = "SPY"

def parse_option_ticker(op_ticker):
    """
    Parses standard OCC: SPY251219C00500000
    Returns (expiry, type, strike)
    """
    clean = op_ticker.replace("O:", "")
    # Regex: ([A-Z]+)(\d{6})([CP])(\d{8})
    match = re.match(r"([A-Z]+)(\d{6})([CP])(\d{8})", clean)
    if match:
        sym, yymmdd, cp, strike_str = match.groups()
        try:
             expiry = datetime.strptime(yymmdd, "%y%m%d").date()
             strike = float(strike_str) / 1000.0
             return {
                "strike": strike,
                "type": "call" if cp == 'C' else "put",
                "expiration": expiry
             }
        except:
             return None
    return None

def process_file(csv_PATH, engine):
    filename = os.path.basename(csv_PATH)
    # Expected: options_YYYY-MM-DD.csv
    date_match = re.search(r"options_(\d{4}-\d{2}-\d{2})\.csv", filename)
    if not date_match:
        return

    file_date_str = date_match.group(1)
    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
    
    output_filename = f"SPY_profile_{file_date_str.replace('-', '')}.parquet"
    output_path = os.path.join(HISTORY_DIR, output_filename)
    
    if os.path.exists(output_path):
        print(f"Skipping {file_date_str}: Already exists.")
        return

    print(f"Processing {file_date_str}...")
    
    try:
        # Load filtering for SPY
        # The file header: day,underlying_ticker,option_ticker,open_interest,implied_volatility,gamma,delta
        
        # Read only SPY rows
        # We can't filter while reading easily with pandas read_csv unless using iterator
        # But given it's "Massive", let's use chunks.
        
        chunk_size = 100000
        spy_dfs = []
        
        for chunk in pd.read_csv(csv_PATH, chunksize=chunk_size):
            # Check column names standard
            chunk.columns = [c.strip() for c in chunk.columns] 
            
            if 'underlying_ticker' in chunk.columns:
                filtered = chunk[chunk['underlying_ticker'] == TICKER]
                if not filtered.empty:
                    spy_dfs.append(filtered)
            elif 'ticker' in chunk.columns: # Fallback if slightly different format
                 # Assuming underlying ticker
                 filtered = chunk[chunk['ticker'] == TICKER]
                 if not filtered.empty:
                    spy_dfs.append(filtered)
                    
        if not spy_dfs:
            print(f"No SPY data in {filename}")
            return
            
        df_spy = pd.concat(spy_dfs)
        
        # Prepare DF for GEX Engine
        # Engine needs: [strike, type, expiration, oi, gamma, iv]
        # We need to parse 'option_ticker' to get strike/type/expiration
        
        parsed_list = []
        for idx, row in df_spy.iterrows():
            op_tick = row.get('option_ticker')
            if not op_tick: continue
            
            p = parse_option_ticker(op_tick)
            if p:
                parsed_list.append({
                    "strike": p['strike'],
                    "type": p['type'],
                    "expiration": str(p['expiration']),
                    "oi": row.get('open_interest', 0),
                    "gamma": row.get('gamma', 0),
                    "iv": row.get('implied_volatility', 0)
                })
        
        if not parsed_list:
             print(f"Failed to parse any options for {filename}")
             return
             
        df_ready = pd.DataFrame(parsed_list)
        
        # Calculate Metadata Spot Price
        # GEX Engine calculate_gex_from_frame typically needs a spot price.
        # But for historical, we might not have it in this file?
        # Maybe we can fetch from yfinance using the date? 
        # Or maybe it's fine to pass 0 if we just want the profile sum (which uses spot)?
        # Wait, Gamma * OI * Spot^2. We NEED Spot.
        # Let's try to get close from yfinance history.
        
        import yfinance as yf
        try:
            # Hacky: fetch 1d history for that date?
            # Or just fetch range covering that date.
            # Ideally we have a local price DB.
            # For now, let's fetch.
            # yf.download(SPY, start=file_date, end=file_date+1d)
            # Use engine's own fetch method if possible, or manual.
            
            # Correction: yfinance might not support exact historical day lookup reliably without full history.
            # Let's assume user has price data?
            # Or just fetch full history once outside loop?
            pass
        except:
            pass
            
        # Optimization: Fetch spot map once
        
        spot = spot_map.get(file_date_str)
        if not spot:
             print(f"Warning: No spot price for {file_date_str}. Skipping.")
             return

        result = engine.calculate_gex_from_frame(TICKER, df_ready, spot_price=spot, as_of=file_date)
        
        if result and "profile" in result:
             # Save Profile to Parquet
             df_prof = pd.DataFrame(result["profile"])
             df_prof.to_parquet(output_path)
             print(f"Saved {output_filename}")
        else:
             print(f"Empty result for {file_date_str}")

    except Exception as e:
        print(f"Error {filename}: {e}")

# Global Spot Cache
spot_map = {}

def load_spot_history():
    print("Loading Spot Price History for SPY...")
    import yfinance as yf
    try:
        # Fetch last 2 years
        df = yf.download(TICKER, period="2y", interval="1d", progress=False)
        # Map date str to Close
        for idx, row in df.iterrows():
            d_str = idx.strftime("%Y-%m-%d")
            # YF often returns multiIndex columns in new versions
            # Check if Close is scalar or Series
            val = row['Close']
            if isinstance(val, pd.Series):
                 val = val.iloc[0]
            spot_map[d_str] = float(val)
    except Exception as e:
        print(f"Failed to load spot history: {e}")

if __name__ == "__main__":
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
        
    engine = GEXEngine()
    load_spot_history()
    
    files = sorted(glob.glob(os.path.join(DATA_DIR, "options_*.csv")))
    print(f"Found {len(files)} files.")
    
    for f in files:
        process_file(f, engine)
