
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from mie_lib.data_ingest.yfinance_loader import read_tickers
from mie_lib.utils.paths import DATA_DIR, RAW_DIR

LOG = logging.getLogger(__name__)

ANALYTICS_DIR = DATA_DIR / "analytics"

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculates ATR using Wilder's Smoothing.
    Expects df to have 'high', 'low', 'close' columns.
    Adds 'atr' column to df.
    """
    df = df.copy()
    
    # Calculate True Range (TR)
    df['h-l'] = df['high'] - df['low']
    df['h-c'] = np.abs(df['high'] - df['close'].shift(1))
    df['l-c'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-c', 'l-c']].max(axis=1)
    
    # Wilder's Smoothing for ATR
    # ewm(alpha=1/period, adjust=False) matches Wilder's smoothing
    df['atr'] = df['tr'].ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    # Cleanup temp columns
    df.drop(columns=['h-l', 'h-c', 'l-c', 'tr'], inplace=True)
    
    return df

def calculate_volatility_metrics(df: pd.DataFrame, lookback_days: int = 126) -> pd.DataFrame:
    """
    Calculates ATR Rank (percentile over lookback_days) and ATR Percent.
    Expects 'atr' and 'close' columns.
    """
    if 'atr' not in df.columns:
        return df

    # ATR Percent (Normalized Volatility)
    df['atr_percent'] = (df['atr'] / df['close']) * 100
    
    # ATR Rank (Rolling Percentile)
    # We want to know where the current ATR sits relative to the last N days
    # defined as: (count(past_N < current) / N) * 100
    
    def rolling_percentile(dat):
        if len(dat) < 1:
            return np.nan
        current = dat[-1]
        return (np.sum(dat < current) / len(dat)) * 100

    # Increase min_periods to ensure statistical significance, but allow some ramp up
    df['atr_rank'] = df['atr'].rolling(window=lookback_days, min_periods=lookback_days//2).apply(rolling_percentile, raw=True)
    
    return df

def get_volatility_regime(row, prev_row):
    """
    Determines Market Regime based on Volatility Rules.
    
    Rules:
    1. Squeeze: ATR Rank < 20
    2. Expansion: ATR Rank > 80
    3. Trend Strength: Price Rising & ATR Rising & ATR Rank > 50
    4. Neutral: Else
    """
    atr_rank = row.get('atr_rank', np.nan)
    close = row.get('close', np.nan)
    prev_close = prev_row.get('close', np.nan) if prev_row is not None else np.nan
    atr = row.get('atr', np.nan)
    prev_atr = prev_row.get('atr', np.nan) if prev_row is not None else np.nan

    if pd.isna(atr_rank):
        return "Unknown", "Insufficient Data"

    # 1. Squeeze (Opportunity)
    if atr_rank < 20:
        return "Squeeze", "⚠️ Squeeze Detect: Volatility is at 6-month lows. Expect a violent breakout move soon."

    # 2. Expansion (High Risk)
    if atr_rank > 80:
        return "Expansion", "🛑 High Volatility: Price range is widely expanded. Adjust position sizing for higher risk."

    # 3. Trend Strength
    # Price Rising (Close > Prev Close) AND ATR Rising (ATR > Prev ATR) AND Rank > 50
    if (pd.notna(close) and pd.notna(prev_close) and close > prev_close and
        pd.notna(atr) and pd.notna(prev_atr) and atr > prev_atr and
        atr_rank > 50):
        return "Trend Strength", "✅ Strong Momentum: Volatility is supporting the trend. Move is likely genuine."

    # 4. Neutral
    return "Neutral", "ℹ️ Normal Activity: Standard volatility conditions."

def calculate_and_save_volatility():
    """
    Calculates Volatility metrics for all tickers and saves daily snapshot.
    """
    tickers = read_tickers()
    results = []
    
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    
    LOG.info(f"Starting Volatility Analysis for {len(tickers)} tickers...")
    
    for ticker in tickers:
        ticker = ticker.strip().upper()
        raw_path = RAW_DIR / f"{ticker}.parquet"
        
        if not raw_path.exists():
            continue
            
        try:
            df = pd.read_parquet(raw_path)
            
            # Normalize Columns
            required = ['date', 'high', 'low', 'close']
            if not all(c in df.columns for c in required):
                df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)
            
            if not all(c in df.columns for c in required):
                LOG.warning(f"Skipping {ticker}: Missing required columns")
                continue
                
            df.sort_values('date', inplace=True)
            
            # 1. Calculate ATR
            df = calculate_atr(df, period=14)
            
            # 2. Calculate Metrics (Rank, %)
            df = calculate_volatility_metrics(df, lookback_days=126)
            
            if len(df) < 2:
                continue

            # Get Latest Data
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            current_atr = last_row.get('atr', np.nan)
            current_rank = last_row.get('atr_rank', np.nan)
            current_pct = last_row.get('atr_percent', np.nan)
            
            if pd.isna(current_atr) or pd.isna(current_rank):
                continue
                
            # 3. Determine Regime
            regime, description = get_volatility_regime(last_row, prev_row)
            
            results.append({
                "date": last_row['date'],
                "ticker": ticker,
                "atr": float(current_atr),
                "atr_rank": float(current_rank),
                "atr_percent": float(current_pct),
                "volatility_regime": regime,
                "volatility_desc": description
            })
            
        except Exception as e:
            LOG.error(f"Error processing Volatility for {ticker}: {e}")
            
    # Save Aggregate
    if results:
        df_out = pd.DataFrame(results)
        out_path = ANALYTICS_DIR / "volatility_daily.parquet"
        df_out.to_parquet(out_path, index=False)
        LOG.info(f"Saved Volatility Analysis to {out_path} ({len(df_out)} tickers)")
    else:
        LOG.warning("No Volatility results generated.")

if __name__ == "__main__":
    import sys
    # Basic logging setup for standalone run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    calculate_and_save_volatility()
