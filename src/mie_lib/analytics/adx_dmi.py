
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from mie_lib.data_ingest.yfinance_loader import read_tickers

LOG = logging.getLogger(__name__)

ANALYTICS_DIR = Path("data/analytics")
RAW_DIR = Path("data/raw")

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculates ADX, +DI, -DI using Wilder's Smoothing.
    Expects df to have 'high', 'low', 'close' columns.
    """
    df = df.copy()
    
    # Calculate True Range (TR)
    df['h-l'] = df['high'] - df['low']
    df['h-c'] = np.abs(df['high'] - df['close'].shift(1))
    df['l-c'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-c', 'l-c']].max(axis=1)
    
    # Calculate Directional Movement (DM)
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    # Wilder's Smoothing Function
    def wilder_smooth(series, period):
        return series.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # Smooth TR and DM
    # Note: Wilder's original formula uses a specific smoothing which is effectively EMA with alpha=1/n
    # Some implementations start with an SMA. Pandas ewm(alpha=1/period) is a close approximation and standard in many libs.
    # To be precise with Wilder, usually the first value is SMA, then subsequent are (prev * (n-1) + curr) / n.
    # ewm(alpha=1/n, adjust=False) does exactly this recurrence.
    
    df['atr'] = wilder_smooth(df['tr'], period)
    df['plus_di'] = 100 * (wilder_smooth(df['plus_dm'], period) / df['atr'])
    df['minus_di'] = 100 * (wilder_smooth(df['minus_dm'], period) / df['atr'])
    
    # Calculate DX
    df['dx'] = 100 * np.abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    
    # Calculate ADX (Smoothed DX)
    df['adx'] = wilder_smooth(df['dx'], period)
    
    return df

def calculate_and_save_adx():
    """
    Calculates ADX/DMI for all tickers and saves daily status.
    """
    tickers = read_tickers()
    results = []
    
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    
    for ticker in tickers:
        ticker = ticker.strip().upper()
        raw_path = RAW_DIR / f"{ticker}.parquet"
        
        if not raw_path.exists():
            LOG.warning(f"Raw data not found for {ticker}, skipping ADX.")
            continue
            
        try:
            df = pd.read_parquet(raw_path)
            
            # Ensure required columns
            required = ['date', 'high', 'low', 'close']
            if not all(c in df.columns for c in required):
                # allow capitalized
                df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)
            
            if not all(c in df.columns for c in required):
                LOG.warning(f"Missing columns in {ticker} data, skipping ADX.")
                continue
                
            df.sort_values('date', inplace=True)
            
            # Run ADX Calculation
            df_adx = calculate_adx(df, period=14)
            
            # Get Latest
            if len(df_adx) < 2:
                 continue
                 
            last_row = df_adx.iloc[-1]
            prev_row = df_adx.iloc[-2]
            
            cur_adx = last_row.get('adx', np.nan)
            cur_pdi = last_row.get('plus_di', np.nan)
            cur_mdi = last_row.get('minus_di', np.nan)
            prev_adx = prev_row.get('adx', np.nan)
            
            if pd.isna(cur_adx) or pd.isna(cur_pdi) or pd.isna(cur_mdi):
                continue
                
            # Status Flags
            is_strong = bool(cur_adx > 25)
            is_uptrend = bool(cur_pdi > cur_mdi)
            is_accelerating = bool(cur_adx > prev_adx)
            
            results.append({
                "date": last_row['date'],
                "ticker": ticker,
                "adx": float(cur_adx),
                "plus_di": float(cur_pdi),
                "minus_di": float(cur_mdi),
                "is_adx_strong": is_strong,
                "is_adx_uptrend": is_uptrend,
                "is_adx_accelerating": is_accelerating
            })
            
        except Exception as e:
            LOG.error(f"Error processing ADX for {ticker}: {e}")
            
    # Save Aggregate
    if results:
        df_out = pd.DataFrame(results)
        out_path = ANALYTICS_DIR / "adx_daily.parquet"
        df_out.to_parquet(out_path, index=False)
        LOG.info(f"Saved daily ADX/DMI status to {out_path} ({len(df_out)} tickers)")
    else:
        LOG.warning("No ADX results generated.")

