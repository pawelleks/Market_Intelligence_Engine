import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
from datetime import datetime

# Ensure project root is in path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.mie_lib.data_ingest.macro.providers.fred import FredProvider
from src.mie_lib.utils.paths import DATA_DIR

PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("minsky_calculator")

def calculate_minsky_indicators():
    try:
        LOG.info("Initializing Minsky Financial Instability Model Calculation...")
        
        # 1. Define Tickers based on Config & Minsky Logic
        # Minsky Section Tickers
        minsky_tickers = [
            'BCNSDODNS',        # Nonfinancial Corporate Debt (Billions)
            'NCBCMDPMVCE',      # Corp Debt to Equity Ratio
            'QUSPAM770A',       # Total Credit to Private Non-Financial Sector (% of GDP)
            'CPATAX',           # Corporate Profits After Tax (Billions, SAAR)
            'CNCF',             # Corporate Net Cash Flow (Total, Billions) - Replaced invalid NCBCF
            'GDP',              # Gross Domestic Product (Nominal Billions) - Replaced A446...
            'LABSHPUSA156NRUG', # Labor Share of Income
            'CAPUTLB50001SQ',   # Capacity Utilization (Percent)
            'BAA10Y',           # BAA - 10Y Spread (Percent)
            'DGS10'             # 10Y Treasury Yield (Percent) - Needed for BAA Yield construction
        ]
        
        provider = FredProvider()
        dfs = []

        # 2. Fetch and Resample Data
        for ticker in minsky_tickers:
            df = provider.fetch_series(ticker)
            if df.empty:
                LOG.warning(f"Warning: No data found for {ticker}")
                continue
            
            # Resample to Quarterly Start ('QS')
            # Most economic data is fine with mean() resampling for aggregation/alignment
            # BCNSDODNS is a stock (Level), but FRED dates it at 01-01 etc. 
            resampled = df.set_index('date').resample('QS').mean()
            
            resampled.rename(columns={'value': ticker}, inplace=True)
            dfs.append(resampled)

        if not dfs:
            LOG.error("No data fetched. Exiting.")
            return

        # 3. Merge into Single DataFrame
        # Outer join to keep all history, sort by date
        minsky_df = pd.concat(dfs, axis=1).sort_index()
        
        # Propagate Annual Labor Share to recent quarters (it matches slowly)
        if 'LABSHPUSA156NRUG' in minsky_df.columns:
            # Linear interpolation for smoother annual-to-quarterly transition
            minsky_df['LABSHPUSA156NRUG'] = minsky_df['LABSHPUSA156NRUG'].interpolate(method='linear')

        # Forward fill purely to handle minor misalignments if any, but economic data usually gaps.
        # Actually, let's strictly forward fill mostly for the daily components (rates) if mapping to quarterly 
        # but resample already handled it.
        # We will drop rows where core components are missing to avoid bad calcs.
        minsky_df = minsky_df.dropna(subset=['BCNSDODNS', 'CPATAX', 'BAA10Y', 'DGS10', 'GDP'])

        LOG.info(f"Data Loaded: {len(minsky_df)} quarterly records.")

        # 4. Calculate Derived Series
        
        # --- Helper Calculations ---
        # Construct BAA Yield (Risk Spread + Risk Free)
        columns_to_keep = []
        
        # Use simple addition for yield proxy if present
        minsky_df['implied_baa_yield'] = minsky_df['BAA10Y'] + minsky_df['DGS10']

        # --- Minsky Indicators ---

        # A. Debt Service Proxy
        # Formula: (Nonfinancial Corp Debt * BAA Corp Yield) / Corp Profits After Tax
        # Interest Cost estimate = Debt * (Yield/100) -> Yield is percent e.g. 5.0
        # Proxy = (Interest Cost) / Profits
        minsky_df['debt_service_proxy'] = (minsky_df['BCNSDODNS'] * minsky_df['implied_baa_yield']) / minsky_df['CPATAX']

        # B. Leverage Ratio
        # Formula: Nonfinancial Corp Debt / GDP (Nominal)
        # We now have GDP directly.
        minsky_df['leverage_ratio'] = minsky_df['BCNSDODNS'] / minsky_df['GDP']

        # C. Minsky Instability Gap
        # Formula: (YoY % Change in Corp Debt) - (YoY % Change in Corp Profits)
        # YoY is 4 quarters.
        debt_yoy = minsky_df['BCNSDODNS'].pct_change(4) * 100
        profits_yoy = minsky_df['CPATAX'].pct_change(4) * 100
        minsky_df['minsky_instability_gap'] = debt_yoy - profits_yoy

        # D. Risk Complacency Index
        # Formula: 1 / (BAA Corp Yield - 10Y Treasury Yield) = 1 / BAA10Y (Spread)
        # Handle division by zero just in case
        minsky_df['risk_complacency_index'] = 1 / minsky_df['BAA10Y']

        # E. Profit Squeeze
        # Formula: Labor Share of Income (normalized)
        # We use Z-Score Standardization: (x - mean) / std
        labor_share = minsky_df['LABSHPUSA156NRUG']
        minsky_df['profit_squeeze'] = (labor_share - labor_share.mean()) / labor_share.std()

        # 5. Save to Parquet
        output_file = PROCESSED_DATA_DIR / "minsky_model.parquet"
        # Ensure directory exists (it should, but safety first)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Select final columns
        final_columns = [
            'debt_service_proxy', 
            'leverage_ratio', 
            'minsky_instability_gap', 
            'risk_complacency_index', 
            'profit_squeeze',
            # Include raw inputs for context if needed, but per spec stick to derived + key source?
            # User said "Create a Pandas DataFrame for them [the derived series]".
            # We will keep just the derived ones + context maybe. 
            # Let's save the derived ones.
        ]
        
        output_df = minsky_df[final_columns].copy()
        
        output_df.to_parquet(output_file, compression='snappy')
        LOG.info(f"Saved Minsky Model data to {output_file}")

        # 6. Logging Summary
        print("\n--- Minsky Model: Latest Indicators ---")
        latest = output_df.iloc[-1]
        print(f"Date: {latest.name.date()}")
        print(f"Debt Service Proxy:       {latest['debt_service_proxy']:.2f}")
        print(f"Leverage Ratio:           {latest['leverage_ratio']:.2f}")
        print(f"Instability Gap:          {latest['minsky_instability_gap']:.2f} (Positive = Ponzi)")
        print(f"Risk Complacency Index:   {latest['risk_complacency_index']:.2f} (Higher = Euphoria)")
        print(f"Profit Squeeze (Z-Score): {latest['profit_squeeze']:.2f}")
        print("---------------------------------------")

        # =========================================================
        # MARKET VALIDATION (STEP 2: Merge with SP500/SPY)
        # =========================================================
        LOG.info("Creating Market Validation Dataset (Daily)...")
        
        # A. Load SPY Data (Full History)
        spy_path = DATA_DIR / "raw" / "SPY.parquet"
        if not spy_path.exists():
            LOG.warning(f"SPY.parquet not found at {spy_path}. Skipping Market Validation.")
            return

        spy_df = pd.read_parquet(spy_path)
        
        # Robust Date/Index Handling
        # Can be 'Date', 'date', or already in index
        date_col = None
        for col in spy_df.columns:
            if col.lower() == 'date':
                date_col = col
                break
                
        if date_col:
            spy_df = spy_df.set_index(date_col)
        
        # Ensure DatetimeIndex and TZ Naive
        spy_df.index = pd.to_datetime(spy_df.index)
        if spy_df.index.tz is not None:
             spy_df.index = spy_df.index.tz_localize(None)
            
        spy_df = spy_df.sort_index()
        
        # Pick Close Price
        if 'Close' in spy_df.columns:
            market_data = spy_df[['Close']].rename(columns={'Close': 'SP500'})
        elif 'close' in spy_df.columns:
            market_data = spy_df[['close']].rename(columns={'close': 'SP500'})
        else:
            market_data = spy_df.iloc[:, 0].to_frame(name='SP500')
            
        # B. Fetch USREC (Recession)
        usrec = provider.fetch_series('USREC')
        if not usrec.empty:
            usrec = usrec.set_index('date')
            usrec.index = pd.to_datetime(usrec.index) 
            if usrec.index.tz is not None:
                usrec.index = usrec.index.tz_localize(None)
                
            usrec = usrec.resample('D').ffill()
            usrec.rename(columns={'value': 'USREC'}, inplace=True)
            
            # Join USREC to SPY (Left Join)
            market_data = market_data.join(usrec, how='left')
        
        # C. Upsample Minsky Data & Merge
        # Minsky Output Index might be named 'date' or have TZ issues?
        # output_df comes from minsky_df, which comes from FredProvider, usually TZ-naive.
        # But let's be safe.
        output_df.index = pd.to_datetime(output_df.index)
        if output_df.index.tz is not None:
            output_df.index = output_df.index.tz_localize(None)
            
        minsky_daily = output_df.resample('D').ffill()
        
        # Merge Minsky onto SPY (Left Join)
        validation_df = market_data.join(minsky_daily, how='left')
             
        # D. Create Regime Indicator
        def classify_regime(row):
             gap = row.get('minsky_instability_gap', -999)
             risk = row.get('risk_complacency_index', -999)
             
             if pd.isna(gap) or gap == -999: return 'Unknown'
             
             if gap > 0:
                 if risk > 0.5:
                     return 'Ponzi'
                 else:
                     return 'Speculative'
             return 'Hedge'

        validation_df['minsky_regime'] = validation_df.apply(classify_regime, axis=1)
        validation_df['USREC'] = validation_df['USREC'].fillna(0)
             
        # Save
        val_file = PROCESSED_DATA_DIR / "minsky_market_validation.parquet"
        validation_df.to_parquet(val_file, compression='snappy')
        LOG.info(f"Saved Market Validation data to {val_file}. Records: {len(validation_df)}")

    except Exception as e:
        LOG.exception(f"Failed to calculate Minsky Model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    calculate_minsky_indicators()
