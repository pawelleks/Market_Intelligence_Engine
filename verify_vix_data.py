
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import sys
import os

# Add src to path to import from mie_lib if needed, or just replicate the simple fetch logic
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from mie_lib.data_ingest.data_aligner import _fetch_single_asset
except ImportError:
    # Fallback if import fails (though it should work)
    print("Could not import _fetch_single_asset, redefining it.")
    def _fetch_single_asset(ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        try:
            df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, progress=False)
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return pd.DataFrame()
        
        if df is None or df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(col[0]) if isinstance(col, tuple) else str(col) for col in df.columns]

        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        df = df.reset_index().rename(columns={'date': 'Date'}).sort_values('Date')
        
        # Select price
        price_col = 'adj_close' if 'adj_close' in df.columns else 'close'
        if price_col in df.columns:
            df['Price'] = pd.to_numeric(df[price_col], errors='coerce').astype('float32')
        else:
            return pd.DataFrame()
            
        return df.set_index('Date')[['Price']]

def main():
    print("Auditing VIX data fetching...")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=365) # 1 Year looking back
    
    tickers = {
        "VIX1D": "^VIX1D",
        "VIX": "^VIX",
        "VIX3M": "^VIX3M"
    }
    
    data_frames = {}
    for name, ticker in tickers.items():
        print(f"Fetching {name} ({ticker})...")
        df = _fetch_single_asset(ticker, start_date, end_date)
        if not df.empty and 'Price' in df.columns:
            # The original _fetch_single_asset returns all columns (Open, High, Low, Close, Price)
            # We only want Price for this comparison
            data_frames[name] = df[['Price']].rename(columns={'Price': name})
        else:
            print(f"Warning: No data for {name}")

    if not data_frames:
        print("No data fetched.")
        return

    # Align
    print("Aligning data...")
    # Start with VIX as base
    if "VIX" in data_frames:
        aligned_df = data_frames["VIX"]
    else:
        aligned_df = next(iter(data_frames.values()))
        
    for name, df in data_frames.items():
        if name == "VIX": continue # Already base or handled
        if "VIX" not in data_frames and df is aligned_df: continue
        
        aligned_df = aligned_df.merge(df, left_index=True, right_index=True, how='outer')
        
    aligned_df = aligned_df.sort_index()
    
    print("\n--- Combined VIX Term Structure DataFrame (First 5 rows) ---")
    print(aligned_df.head())
    print("\n--- Tail ---")
    print(aligned_df.tail())
    
    # Check for NaN alignment issues
    print("\n--- NaN Counts ---")
    print(aligned_df.isna().sum())

if __name__ == "__main__":
    main()
