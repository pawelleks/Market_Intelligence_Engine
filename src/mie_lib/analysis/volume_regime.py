import pandas as pd
import numpy as np

def compute_volume_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame with 'close' and 'volume', computes the 20-day volume ratio and SMAs.
    Requires at least 20 rows to compute the 20-period rolling metrics properly.
    """
    df = df.copy()
    
    # 1. Price Change
    df["prev_close"] = df["close"].shift(1)
    df["price_change"] = df["close"] - df["prev_close"]
    
    # 2. Assign Up and Down Volume
    df["up_vol"] = np.where(df["price_change"] > 0, df["volume"], 0)
    df["down_vol"] = np.where(df["price_change"] < 0, df["volume"], 0)
    
    # 3. 20-Day Rolling Sums
    df["roll_up_vol"] = df["up_vol"].rolling(window=20).sum()
    df["roll_down_vol"] = df["down_vol"].rolling(window=20).sum()
    
    # 4. Up/Down Volume Ratio
    # Safe division to avoid ZeroDivisionError
    df["ud_vol_ratio"] = np.where(
        df["roll_down_vol"] == 0, 
        np.where(df["roll_up_vol"] > 0, 100.0, 1.0),
        df["roll_up_vol"] / df["roll_down_vol"]
    )
    
    # Additional Context Metrics
    df["sma20"] = df["close"].rolling(window=20).mean()
    df["vol_mean_20d"] = df["volume"].rolling(window=20).mean()
    
    # 20-Day return
    df["price_20d_ago"] = df["close"].shift(20)
    df["price_change_20d"] = (df["close"] - df["price_20d_ago"]) / df["price_20d_ago"]
    
    # 20-Day High/Low for Consolidation checks
    df["high_20d"] = df["close"].rolling(window=20).max()
    df["low_20d"] = df["close"].rolling(window=20).min()
    
    return df

def classify_market_state(row: pd.Series) -> str:
    """
    Evaluates a single day's computed metrics to determine the Market Regime.
    """
    if pd.isna(row.get("sma20")):
        return "Insufficient Data"

    current_price = float(row.get("close", 0))
    current_volume = float(row.get("volume", 0))
    volume_mean_20d = float(row.get("vol_mean_20d", 0))
    price_change_20d = float(row.get("price_change_20d", 0))
    current_ratio = float(row.get("ud_vol_ratio", 1.0))
    sma20 = float(row.get("sma20", 0))
    high_20 = float(row.get("high_20d", 0))
    low_20 = float(row.get("low_20d", 0))
    
    # 1. Capitulation Check
    if price_change_20d < -0.10 and current_volume > (2 * volume_mean_20d):
        return "Capitulation"
        
    # 2. Distribution Check
    elif (current_price > sma20) and (current_ratio < 1.0):
        return "Distribution"
        
    # 3. Accumulation Check
    elif (current_price <= sma20 or price_change_20d < 0.02) and (current_ratio > 1.2):
        return "Accumulation"
        
    # 4. Consolidation Check
    else:
        range_pct = (high_20 - low_20) / current_price if current_price > 0 else 0
        if range_pct < 0.05 and current_volume < volume_mean_20d:
             return "Consolidation"
             
    # 5. Default
    return "Neutral"
