
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from statsmodels.tsa.filters.hp_filter import hpfilter

# Set up paths
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.mie_lib.data_ingest.macro.providers.fred import FredProvider
from src.mie_lib.utils.paths import PROCESSED_DATA_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger("hp_model")

def generate_hp_model():
    LOG.info("Initializing Hodrick-Prescott (HP) Filter Model Calculation...")
    
    # 1. Define Tickers
    # GDPC1: Real GDP (Quarterly, starts 1947)
    # TCMDO: Total Credit Market Debt Outstanding (Quarterly, starts 1945)
    #        Previously TOTDTEUSQ163N (started 2005) - Extended 2026-01-10 for historical depth
    # GDPDEF: GDP Deflator (Quarterly, for inflation adjustment)
    tickers = {
        'GDPC1': 'real_gdp',
        'TCMDO': 'nominal_credit',  # Extended from TOTDTEUSQ163N - now goes back to 1945
        'GDPDEF': 'gdp_deflator'
    }
    
    provider = FredProvider()
    dfs = []
    
    # 2. Fetch Data
    for ticker, name in tickers.items():
        LOG.info(f"Fetching FRED series: {ticker} ({name})...")
        df = provider.fetch_series(ticker)
        if df.empty:
            LOG.error(f"No data found for {ticker}. Exiting.")
            return
            
        df = df.set_index('date')
        df.rename(columns={'value': name}, inplace=True)
        dfs.append(df)
        
    # 3. Merge and Clean
    # Use 'outer' join to keep as much data as possible, then drop rows with missing values
    # These series are all quarterly and usually align on quarter start/end
    combined_df = pd.concat(dfs, axis=1).sort_index().dropna()
    LOG.info(f"Data combined: {len(combined_df)} quarterly records.")
    
    # 4. Calculation Logic
    
    # A. Adjust Nominal Credit for Inflation
    # Real Credit = (Nominal Credit / GDP Deflator) * 100
    # Note: GDPDEF base is usually 100
    combined_df['real_credit'] = (combined_df['nominal_credit'] / combined_df['gdp_deflator']) * 100
    
    # B. HP Filter for GDP (Output Gap)
    # Lambda = 1600 for quarterly data
    LOG.info("Applying HP Filter to Real GDP...")
    gdp_cycle, gdp_trend = hpfilter(combined_df['real_gdp'], lamb=1600)
    combined_df['gdp_trend'] = gdp_trend
    combined_df['output_gap'] = (gdp_cycle / gdp_trend) * 100
    
    # C. HP Filter for Credit (Credit Gap)
    LOG.info("Applying HP Filter to Real Credit...")
    credit_cycle, credit_trend = hpfilter(combined_df['real_credit'], lamb=1600)
    combined_df['credit_trend'] = credit_trend
    combined_df['credit_gap'] = (credit_cycle / credit_trend) * 100
    
    # 5. Save results
    output_file = PROCESSED_DATA_DIR / "hp_model.parquet"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare final dataframe
    final_df = combined_df[[
        'real_gdp', 'gdp_trend', 'output_gap',
        'real_credit', 'credit_trend', 'credit_gap'
    ]].copy()
    
    # Ensure index is named 'date'
    final_df.index.name = 'date'
    
    # Save to parquet
    final_df.to_parquet(output_file)
    LOG.info(f"Saved HP Model data to {output_file}")
    
    # Print latest values for verification
    latest = final_df.iloc[-1]
    print("\n--- HP Filter Model: Latest Quarterly Indicators ---")
    print(f"Date:       {final_df.index[-1].strftime('%Y-%m-%d')}")
    print(f"Output Gap: {latest['output_gap']:.2f}%")
    print(f"Credit Gap: {latest['credit_gap']:.2f}%")
    print("----------------------------------------------------\n")

if __name__ == "__main__":
    generate_hp_model()
