
from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
import datetime

loader = MassiveOptionsLoader()
# Try to find recent data. 
# Massive files usually named by date?
# Let's try listing available dates if the loader supports it, or just blindly load recent dates.

today = datetime.date.today()
dims = [today - datetime.timedelta(days=i) for i in range(5)]

print("Checking Massive Data availability...")
for d in dims:
    try:
        df = loader.load_day_aggregates(str(d), tickers=['SPY'])
        if not df.empty:
            print(f"Found data for {d}: {len(df)} rows")
            print(df.columns.tolist())
            break
        else:
            print(f"No data for {d}")
    except Exception as e:
        print(f"Error loading {d}: {e}")
