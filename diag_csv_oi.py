
import pandas as pd
import sys

def analyze_csv():
    csv_path = "data/raw/massive/options/options_2025-12-05.csv"
    print(f"Loading {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Failed to load CSV: {e}")
        return

    # Loading massive loader to parse strikes if needed?
    # The raw csv has 'option_ticker'. It might not have 'strike'.
    # Let's see columns.
    print(f"Columns: {df.columns.tolist()}")
    
    qqq = df[df['underlying_ticker'] == 'QQQ'].copy()
    if qqq.empty:
        print("No QQQ data in CSV.")
        return

    # We need to parse strikes if not present
    if 'strike' not in qqq.columns:
        print("Parsing strikes from option_ticker...")
        # Simple regex or use MassiveOptionsLoader logic
        # format: TICKER YYMMDD T/P SSSSSSSS
        # QQQ 251205 C 00450000
        # last 8 are strike * 1000
        qqq['strike'] = qqq['option_ticker'].apply(lambda x: float(x[-8:]) / 1000.0)
        qqq['type'] = qqq['option_ticker'].apply(lambda x: 'call' if 'C' in x else 'put')
        
    # Check OI distribution
    # Filter for Puts
    puts = qqq[qqq['type'] == 'put']
    
    print("\n--- QQQ Puts Analysis ---")
    print(f"Total Put Rows: {len(puts)}")
    print(f"Total Put OI:   {puts['open_interest'].sum():,.0f}")
    
    # Sort by OI
    top_oi = puts.sort_values('open_interest', ascending=False).head(10)
    print("\nTop 10 Strikes by Open Interest:")
    print(top_oi[['strike', 'open_interest', 'implied_volatility']].to_string(index=False))
    
    # Check 680 range
    range_mask = (puts['strike'] >= 650) & (puts['strike'] <= 700)
    range_puts = puts[range_mask]
    print(f"\n--- Puts in Range 650-700 ---")
    print(f"Count: {len(range_puts)}")
    print(f"Total OI in Range: {range_puts['open_interest'].sum():,.0f}")
    if not range_puts.empty:
        print(range_puts[['strike', 'open_interest', 'implied_volatility']].head(10).to_string(index=False))

if __name__ == "__main__":
    analyze_csv()
