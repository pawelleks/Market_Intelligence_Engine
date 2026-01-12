
import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.mie_lib.data_ingest.macro.providers.fred import FredProvider
from src.mie_lib.utils.paths import DATA_DIR

PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("abct_calculator")

def calculate_abct_indicators():
    try:
        LOG.info("Initializing ABCT (Austrian Business Cycle) Model Calculation...")
        
        # 1. Define Tickers
        abct_tickers = [
            'WPSFD41312',      # PPI Private Capital Equipment (Active)
            'CPIAUCSL',        # CPI All Items (Lower Order)
            'M2SL',            # Money Supply
            'PSAVERT',         # Personal Savings Rate
            'DGS10',           # 10Y Yield
            'FEDFUNDS',        # Fed Funds Rate (Monthly)
            'GDPC1',           # Real GDP (Quarterly, for context)
            'USREC',           # Recessions
            'TOTLL',           # Total Loans & Leases (Credit)
            'PMSAVE'           # Personal Saving Amount (Billions)
        ]
        
        provider = FredProvider()
        dfs = []

        # 2. Fetch and Resample Data (Monthly Baseline)
        for ticker in abct_tickers:
            df = provider.fetch_series(ticker)
            if df.empty:
                LOG.warning(f"Warning: No data found for {ticker}")
                continue
            
            # Resample to Monthly Start ('MS') and forward fill
            # Most are monthly. GDPC1 is quarterly.
            resampled = df.set_index('date').resample('MS').ffill()
            
            resampled.rename(columns={'value': ticker}, inplace=True)
            dfs.append(resampled)

        if not dfs:
            LOG.error("No data fetched. Exiting.")
            return

        # 3. Merge into Single DataFrame
        abct_df = pd.concat(dfs, axis=1).sort_index()
        
        # Drop rows passed 1947 or where key data is missing
        abct_df = abct_df.dropna(subset=['PSAVERT', 'M2SL', 'WPSFD41312'])
        
        LOG.info(f"Data Loaded: {len(abct_df)} monthly records.")

        # 4. Calculate Derived Series
        
        # A. Malinvestment Ratio (Structure of Production) - CONFIRMED
        # Higher Order Prices (Capital Goods) / Lower Order Prices (Consumer Goods)
        base_ppi = abct_df['WPSFD41312'].iloc[0]
        base_cpi = abct_df['CPIAUCSL'].iloc[0]
        
        abct_df['ppi_capital_rebased'] = (abct_df['WPSFD41312'] / base_ppi) * 100
        abct_df['cpi_rebased'] = (abct_df['CPIAUCSL'] / base_cpi) * 100
        
        abct_df['malinvestment_ratio'] = abct_df['ppi_capital_rebased'] / abct_df['cpi_rebased']
        
        # B. Monetary Inflation (M2 YoY)
        abct_df['m2_yoy'] = abct_df['M2SL'].pct_change(12) * 100
        
        # Calculate 6-month Rolling Average for Smooth Signal
        abct_df['m2_yoy_rolling_6m'] = abct_df['m2_yoy'].rolling(window=6).mean()
        
        # C. Savings-Investment Gap (UPDATED Logic)
        # Formula: YoY Growth(Total Credit) - YoY Growth(Savings Amount)
        
        # Calculate YoY Changes for Credit and Savings Amount
        abct_df['credit_growth_yoy'] = abct_df['TOTLL'].pct_change(12) * 100
        abct_df['savings_growth_yoy'] = abct_df['PMSAVE'].pct_change(12) * 100
        
        # Also calculate Rolling Avg for Savings Rate directly (as requested for visualization)
        abct_df['savings_rate_rolling_6m'] = abct_df['PSAVERT'].rolling(window=6).mean()
        
        # The Gap: If Credit grows faster than Savings, it's an Artificial Boom (Positive Gap)
        abct_df['savings_investment_gap'] = abct_df['credit_growth_yoy'] - abct_df['savings_growth_yoy']
        
        # VISUALIZATION GAP (Smoothed for Chart & Banner)
        # Difference between M2 Trend and Savings Rate Trend
        abct_df['credit_savings_gap'] = abct_df['m2_yoy_rolling_6m'] - abct_df['savings_rate_rolling_6m']
        
        # D. Wicksellian Spread Proxy (UPDATED Logic: Rate Distortion)
        # Formula: Natural Rate Proxy (Real GDP Growth + CPI) - Fed Funds Rate
        # Signal: Positive & High -> Rates "Artificially Low" (Boom).
        
        # Calculate Real GDP Growth (YoY) - Note: GDPC1 is ffilled, so we take 12 month change
        # But GDPC1 updates quarterly. 12 month change on ffilled data is step-wise but acceptable proxy.
        abct_df['real_gdp_growth'] = abct_df['GDPC1'].pct_change(12) * 100
        
        # Calculate CPI YoY
        abct_df['cpi_yoy'] = abct_df['CPIAUCSL'].pct_change(12) * 100
        
        # Natural Rate Proxy = Real Growth + Inflation
        abct_df['natural_rate_proxy'] = abct_df['real_gdp_growth'] + abct_df['cpi_yoy']
        
        # Spread = Natural Rate - Fed Funds
        abct_df['wicksellian_spread'] = abct_df['natural_rate_proxy'] - abct_df['FEDFUNDS']
        
        # E. ABCT Composite "Boom" Signal (Refined)
        # 1. Rising Malinvestment Ratio (Momentum)
        # 2. Positive Savings-Investment Gap (Credit funded)
        # 3. Positive Wicksellian Spread (Rates too low)
        
        # Normalize inputs (Z-Scores)
        gap_z = (abct_df['savings_investment_gap'] - abct_df['savings_investment_gap'].mean()) / abct_df['savings_investment_gap'].std()
        
        spread_z = (abct_df['wicksellian_spread'] - abct_df['wicksellian_spread'].mean()) / abct_df['wicksellian_spread'].std()
        
        ratio_yoy = abct_df['malinvestment_ratio'].pct_change(12) * 100
        ratio_z = (ratio_yoy - ratio_yoy.mean()) / ratio_yoy.std()
        
        # Composite Boom Score (Equal Weight)
        abct_df['abct_boom_score'] = (gap_z + spread_z + ratio_z) / 3

        # 5. Save to Parquet
        output_file = PROCESSED_DATA_DIR / "abct_model.parquet"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Select final columns
        final_columns = [
            'malinvestment_ratio',
            'm2_yoy',
            'm2_yoy_rolling_6m',
            'savings_investment_gap',
            'credit_savings_gap', # Added for visualization
            'savings_growth_yoy', # Added for context
            'savings_rate_rolling_6m',
            'credit_growth_yoy',  # Added for context
            'wicksellian_spread',
            'natural_rate_proxy', # Added for context
            'abct_boom_score',
            'PSAVERT',
            'USREC',
            'ppi_capital_rebased',
            'cpi_rebased',
            'FEDFUNDS'
        ]
        
        output_df = abct_df[final_columns].copy()
        
        # Ensure NaNs are filled (e.g. first 12 months for YoY)
        output_df = output_df.fillna(0)
        
        output_df.to_parquet(output_file, compression='snappy')
        LOG.info(f"Saved ABCT Model data to {output_file}")
        
        # Logging Summary
        print("\n--- ABCT Model: Latest Indicators ---")
        latest = output_df.iloc[-1]
        print(f"Date: {latest.name.date()}")
        print(f"Malinvestment Ratio:   {latest['malinvestment_ratio']:.2f}")
        print(f"Savings-Invest Gap:    {latest['savings_investment_gap']:.2f}% (Credit - Savings)")
        print(f"Wicksellian Spread:    {latest['wicksellian_spread']:.2f}% (Nat Rate - Fed Funds)")
        print(f"Boom Score (Z):        {latest['abct_boom_score']:.2f}")
        print("-------------------------------------")

    except Exception as e:
        LOG.exception(f"Failed to calculate ABCT Model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    calculate_abct_indicators()
