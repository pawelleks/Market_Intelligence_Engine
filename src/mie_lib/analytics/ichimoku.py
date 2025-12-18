import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import logging

from mie_lib.utils.logging import get_logger
from mie_lib.utils.paths import DATA_DIR
from mie_lib.data_ingest.yfinance_loader import read_tickers

LOG = get_logger("analytics")

ANALYTICS_DIR = DATA_DIR / "analytics"
OUTPUT_PATH = ANALYTICS_DIR / "ichimoku_daily.parquet"

def calculate_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Ichimoku Kinko Hyo indicators.
    
    Formulas:
    - Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    - Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    - Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2
    - Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
    - Chikou Span (Lagging Span): Close shifted back 26 periods
    """
    if df is None or df.empty:
        return df

    # Copy to avoid mutation
    d = df.copy()
    
    # Ensure High/Low are available
    if 'high' not in d.columns or 'low' not in d.columns:
        LOG.warning("Missing high/low columns for Ichimoku calculation")
        return pd.DataFrame()

    high = d['high']
    low = d['low']
    close = d['close']

    # 1. Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    nine_period_high = high.rolling(window=9).max()
    nine_period_low = low.rolling(window=9).min()
    d['tenkan_sen'] = (nine_period_high + nine_period_low) / 2

    # 2. Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    twenty_six_period_high = high.rolling(window=26).max()
    twenty_six_period_low = low.rolling(window=26).min()
    d['kijun_sen'] = (twenty_six_period_high + twenty_six_period_low) / 2

    # 3. Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2
    # Plotted 26 periods ahead
    d['senkou_span_a'] = ((d['tenkan_sen'] + d['kijun_sen']) / 2).shift(26)

    # 4. Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
    # Plotted 26 periods ahead
    fifty_two_period_high = high.rolling(window=52).max()
    fifty_two_period_low = low.rolling(window=52).min()
    d['senkou_span_b'] = ((fifty_two_period_high + fifty_two_period_low) / 2).shift(26)

    # 5. Chikou Span (Lagging Span): Close shifted back 26 periods
    # Plotted 26 periods behind (so current close is the value for 26 days ago)
    # The user request says "Close price shifted back 26 periods".
    # Interpretation: The Chikou Span for TODAY is TODAY's Close plotted 26 days ago.
    # However, for analytical "latest" checks, we usually compare TODAY's Chikou (which is today's close)
    # vs the price 26 days ago.
    # Let's add 'chikou_span' as Close shifted -26 (future looking) or simply compare current close vs shifted price?
    # Standard convention: Chikou Span = Close, plotted at t-26.
    # To check "is_chikou_confirmed", we check if Close(t) > Close(t-26).
    d['chikou_span'] = d['close'].shift(-26) # This puts future close into current row? No.
    # Standard: Chikou Span is lagging.
    # The value at time `t` is `Close(t+26)`. Wait, no.
    # At time `t`, Chikou is `Close(t)`. It is displayed at `t-26`.
    # Let's stick to the comparison logic requested: "True if Chikou Span > Price from 26 periods ago".
    # Since Chikou Span at time T is Close(T), we compare Close(T) > Close(T-26).
    
    return d

def calculate_and_save_ichimoku(tickers=None):
    """
    Calculate Ichimoku for tickers and save latest status to parquet.
    """
    if not tickers:
        tickers = read_tickers()

    results = []
    
    for ticker in tickers:
        try:
            # Load raw data
            p_parquet = DATA_DIR / "raw" / f"{ticker}.parquet"
            if not p_parquet.exists():
                LOG.warning(f"No data found for {ticker}, skipping Ichimoku.")
                continue
                
            df = pd.read_parquet(p_parquet)
            if df.empty or len(df) < 52: # Need at least 52 periods for Span B
                continue
                
            # Sort by date
            df = df.sort_values('date').reset_index(drop=True)
            
            # Calculate
            df = calculate_ichimoku(df)
            
            # Get latest row (valid data)
            # Since Span A/B are shifted forward 26 periods, they are NaN for the first 26+rows
            # But wait, Span A/B are plotted 26 periods AHEAD.
            # So `shift(26)` puts existing calculated values into the future.
            # Pandas `shift(26)` moves data DOWN (forward in index).
            # So value calculated at T is moved to T+26.
            # This means for the LATEST date, we have Span A/B values that came from T-26.
            
            latest = df.iloc[-1]
            
            # Logic Checks for Latest Date
            close = latest['close']
            span_a = latest['senkou_span_a']
            span_b = latest['senkou_span_b']
            
            # Is Above Cloud
            is_above_cloud = False
            if pd.notna(close) and pd.notna(span_a) and pd.notna(span_b):
                max_span = max(span_a, span_b)
                is_above_cloud = close > max_span
                
            # Is Cloud Green (Bullish Cloud)
            is_cloud_green = False
            if pd.notna(span_a) and pd.notna(span_b):
                 is_cloud_green = span_a > span_b
                 
            # Is Chikou Confirmed
            # Chikou Span (Current Close) > Price 26 periods ago
            is_chikou_confirmed = False
            if len(df) > 26:
                price_26_ago = df.iloc[-27]['close'] # -1 is current, -27 is 26 ago
                if pd.notna(close) and pd.notna(price_26_ago):
                    is_chikou_confirmed = close > price_26_ago
            
            # Calculate Cloud Age (Consecutive days in current Above/Below state)
            cloud_age = 0
            if len(df) > 0:
                for i in range(len(df) - 1, -1, -1):
                    row = df.iloc[i]
                    c = row['close']
                    sa = row['senkou_span_a']
                    sb = row['senkou_span_b']
                    
                    if pd.isna(c) or pd.isna(sa) or pd.isna(sb):
                        break
                        
                    mx = max(sa, sb)
                    daily_above = c > mx
                    
                    if daily_above == is_above_cloud:
                        cloud_age += 1
                    else:
                        break

            results.append({
                "ticker": ticker,
                "date": latest['date'],
                "tenkan_sen": latest['tenkan_sen'],
                "kijun_sen": latest['kijun_sen'],
                "senkou_span_a": span_a,
                "senkou_span_b": span_b,
                "close": close,
                "is_above_cloud": is_above_cloud,
                "is_cloud_green": is_cloud_green,
                "is_chikou_confirmed": is_chikou_confirmed,
                "cloud_age": cloud_age,
                "updated_at": datetime.now(timezone.utc)
            })
            
        except Exception as e:
            LOG.error(f"Failed to calculate Ichimoku for {ticker}: {e}")
            continue

    if results:
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        final_df = pd.DataFrame(results)
        final_df.to_parquet(OUTPUT_PATH, index=False)
        LOG.info(f"Saved Ichimoku data for {len(results)} tickers to {OUTPUT_PATH}")
    else:
        LOG.warning("No Ichimoku results generated.")

if __name__ == "__main__":
    calculate_and_save_ichimoku()
