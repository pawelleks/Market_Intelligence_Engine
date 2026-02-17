import pandas as pd
try:
    df = pd.read_parquet("data/analytics/gex/SPY_profile.parquet")
    print("Columns:", df.columns.tolist())
    print("First 5 rows:\n", df.head())
    
    # Quick sanity check for walls logic
    if 'total_call_gex' in df.columns:
        call_wall = df.loc[df['total_call_gex'].idxmax(), 'strike']
        print(f"Estimated Call Wall: {call_wall}")
        
    if 'total_put_gex' in df.columns:
        # Puts are usually negative in GEX profile, so minimize (most negative)
        put_wall = df.loc[df['total_put_gex'].idxmin(), 'strike']
        print(f"Estimated Put Wall: {put_wall}")
        
except Exception as e:
    print(e)
