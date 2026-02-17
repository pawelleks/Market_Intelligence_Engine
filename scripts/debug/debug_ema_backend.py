import sys
import os

# Add src to path
sys.path.append(os.getcwd() + "/src")

try:
    from mie_lib.analytics.tools.ema_respect import analyze_ticker
    import pandas as pd
    from mie_lib.utils.paths import DATA_DIR
    
    print("Checking SPY data columns...")
    df = pd.read_parquet(DATA_DIR / "raw" / "SPY.parquet")
    print(f"Columns: {df.columns.tolist()}")

    print("Running analysis for SPY...")
    res = analyze_ticker("SPY", min_period=10, max_period=20) # Short run
    
    if "error" in res:
        print(f"Error: {res['error']}")
    else:
        chart_data = res.get("chart_data", [])
        print(f"Chart Data Length: {len(chart_data)}")
        if chart_data:
            print("First Record Sample:")
            print(chart_data[0])
            print("Last Record Sample:")
            print(chart_data[-1])
            
            # Check for Nones
            none_count = sum(1 for d in chart_data if d['close'] is None)
            print(f"Records with None close: {none_count}")
            
except Exception as e:
    print(f"Execution Error: {e}")
