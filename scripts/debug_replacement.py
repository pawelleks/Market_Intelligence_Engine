
import sys
from pathlib import Path
import logging

# Set up paths
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.mie_lib.data_ingest.macro.providers.fred import FredProvider

# Setup simplistic logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("diagnostic_replacement")

def check_replacement():
    LOG.info("Checking Replacement Ticker WPSFD41312...")
    
    ticker = 'WPSFD41312'
    provider = FredProvider()
    
    df = provider.fetch_series(ticker)
    if df.empty:
        print(f"{ticker:<20} | {'NO DATA':<15} | 0")
        return
        
    max_date = df['date'].max()
    count = len(df)
    
    date_str = max_date.strftime('%Y-%m-%d')
    prefix = "🔴" if max_date.year < 2024 else "🟢"
    print(f"{prefix} {ticker:<18} | {date_str:<15} | {count:<10}")

if __name__ == "__main__":
    check_replacement()
