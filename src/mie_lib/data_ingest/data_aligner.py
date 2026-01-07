import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from mie_lib.analytics.downtrend_engine import DEFAULT_WEIGHTS

def _fetch_single_asset(ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Downloads price data for a single ticker using yfinance."""
    try:
        df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, progress=False)
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()
    
    if df is None or df.empty:
        return pd.DataFrame()

    # Flatten MultiIndex and normalize column names
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(col[0]) if isinstance(col, tuple) else str(col) for col in df.columns]

    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    
    df = df.reset_index().rename(columns={'date': 'Date'}).sort_values('Date')
    
    # Select price column (prefer adj_close)
    price_col = 'adj_close' if 'adj_close' in df.columns else 'close'
    if price_col in df.columns:
        df['Price'] = pd.to_numeric(df[price_col], errors='coerce').astype('float32')
    else:
        # If no price column found, return empty
        return pd.DataFrame()
    
    # Clean index and required columns
    required_ohlc = ['open', 'high', 'low', 'close', 'volume']
    for col in required_ohlc:
        if col not in df.columns:
            df[col] = np.nan # Ensure required columns are present

    return df.set_index('Date')

def fetch_and_align_dcs_assets(ticker: str, end_date: Optional[date] = None, lookback_days: int = 500) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Fetches SPY and auxiliary assets, aligns them on a common Date index, and prepares for scoring.
    """
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    # 1. Define all required tickers
    # The scoring model requires SPY (base), VIX/VIX3M (term), RSP (breadth), HYG/LQD (credit).
    required_tickers = {ticker, '^VIX', '^VIX3M', 'RSP', 'HYG', 'LQD'}
    
    # 2. Fetch all data individually
    data_frames = {}
    for t in required_tickers:
        data_frames[t] = _fetch_single_asset(t, start_date, end_date)
        
    # 3. Align data on SPY's index (or the primary ticker's index)
    spy_df = data_frames.get(ticker, pd.DataFrame()).copy()
    if spy_df.empty:
        # If primary ticker fails, we cannot proceed
        # However, for robustness, we could try SPY if ticker != SPY
        if ticker != 'SPY':
             spy_df = data_frames.get('SPY', pd.DataFrame()).copy()
        
        if spy_df.empty:
            # Return empty DF to signal failure
            return pd.DataFrame(), DEFAULT_WEIGHTS

    # Alignment: Outer merge on Date index
    # Note: We rename 'Price' to '{ticker}_Price'
    aligned_df = spy_df.copy()
    aligned_df = aligned_df.rename(columns={'Price': f'SPY_Price'}) # Force SPY_Price naming convention for engine
    
    if ticker != 'SPY':
         aligned_df = aligned_df.rename(columns={f'{ticker}_Price': 'SPY_Price'})

    for t, df_asset in data_frames.items():
        if t == ticker or df_asset.empty:
            continue

        # Rename the 'Price' column for the auxiliary assets
        col_name = f'{t}_Price'
        if 'Price' in df_asset.columns:
            tmp_df = df_asset[['Price']].rename(columns={'Price': col_name})
            
            # Merge on Date index
            aligned_df = aligned_df.merge(tmp_df, left_index=True, right_index=True, how='left')

    # Forward fill VIX/VIX3M to handle small gaps
    cols_to_ffill = [c for c in aligned_df.columns if 'VIX' in c]
    if cols_to_ffill:
        aligned_df[cols_to_ffill] = aligned_df[cols_to_ffill].ffill(limit=1)

    # 4. Final Cleanup and Signal Preparation (Standardizing column names expected by the engine)
    
    # The engine handles column case normalization, so we don't need to duplicate High/high.
    # We just need to ensure SPY_ret exists.

    # Final Check: Calculate SPY return and ensure it's named 'SPY_ret'
    # The engine expects 'SPY_Price' to exist.
    if 'SPY_Price' not in aligned_df.columns:
         # Fallback if something went wrong with renaming
         if 'Price' in aligned_df.columns:
             aligned_df['SPY_Price'] = aligned_df['Price']
         elif 'close' in aligned_df.columns:
             aligned_df['SPY_Price'] = aligned_df['close']
    
    if 'SPY_Price' in aligned_df.columns:
        aligned_df['SPY_ret'] = aligned_df['SPY_Price'].pct_change().astype('float32')
    else:
        return pd.DataFrame(), DEFAULT_WEIGHTS # Critical failure

    # 5. Fetch HMM Bear Probability (New Integration)
    try:
        from mie_lib.utils.paths import hmm_std_out_dir
        # FIX: Align with Dashboard/Assistant defaults (10y / 3-State)
        hmm_dir = hmm_std_out_dir(ticker, window_years=10, n_states=3)
        hmm_probs_path = hmm_dir / "hmm_probs.parquet"
        
        if hmm_probs_path.exists():
            hmm_df = pd.read_parquet(hmm_probs_path)
            # hmm_df has ['date', 'hmm_prob_bull', 'hmm_prob_bear']
            # We need to merge 'hmm_prob_bear' onto aligned_df
            
            # Ensure date is datetime and tz-naive for merging
            hmm_df['date'] = pd.to_datetime(hmm_df['date']).dt.tz_localize(None)
            
            # Rename for clarity if needed, but engine expects 'hmm_bear_prob'
            hmm_df = hmm_df.rename(columns={'hmm_prob_bear': 'hmm_bear_prob'})
            
            # Merge
            # aligned_df index is Date (datetime)
            # Reset index to merge on column
            aligned_df = aligned_df.reset_index()
            if 'Date' not in aligned_df.columns and 'index' in aligned_df.columns:
                aligned_df = aligned_df.rename(columns={'index': 'Date'})
            
            aligned_df['Date'] = pd.to_datetime(aligned_df['Date']).dt.tz_localize(None)
            
            aligned_df = aligned_df.merge(hmm_df[['date', 'hmm_bear_prob']], left_on='Date', right_on='date', how='left')
            aligned_df = aligned_df.drop(columns=['date']) # Drop redundant date col
            aligned_df = aligned_df.set_index('Date')
            
            # Forward fill HMM probability to handle slight lags in HMM calculation vs latest price
            if 'hmm_bear_prob' in aligned_df.columns:
                aligned_df['hmm_bear_prob'] = aligned_df['hmm_bear_prob'].ffill(limit=10)
            
    except Exception as e:
        print(f"Warning: Failed to load HMM data for {ticker}: {e}")

    return aligned_df.reset_index(), DEFAULT_WEIGHTS
