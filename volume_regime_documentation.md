# Volume Regime Analysis Methodology

This document provides a full explanation and code examples of how the **Volume Regime Analysis** (displayed at `/analysis/volume`) is calculated in the Market Intelligence Engine.

## Overview
The Volume Regime study classifies the current market state of an asset into one of five categories: `Accumulation`, `Distribution`, `Capitulation`, `Consolidation`, or `Neutral`. It bases this classification primarily on the **20-day Up/Down Volume Ratio** juxtaposed against recent price action and volume trends.

This logic serves as a robust gauge of institutional activity—identifying whether large participants are quietly accumulating shares, actively distributing them, or if the market has reached a state of capitulation exhaustion.

---

## 1. Core Metrics Calculation

The crux of the regime analysis revolves around separating trading volume into "Up Volume" and "Down Volume" based on daily price changes, and then analyzing the relationship over a 20-day rolling window.

### Step-by-Step Logic
1. **Price Change**: Calculate the daily price change using the Close price (or Adjusted Close). A day is considered "Green" if the Close is strictly greater than the Previous Close, and "Red" if it is strictly lower.
2. **Directional Volume**: 
   - **Up Volume**: The day's total volume if the price change is positive; otherwise `0`.
   - **Down Volume**: The day's total volume if the price change is negative; otherwise `0`.
3. **20-Day Rolling Sums**: Sum the Up Volume and Down Volume over the trailing 20 trading days.
4. **Up/Down Volume Ratio**: Divide the 20-day Up Volume by the 20-day Down Volume. A ratio above `1.0` indicates more volume on up days (buying pressure), while a ratio below `1.0` indicates more volume on down days (selling pressure).

### Code Example: Metric Calculation
```python
import pandas as pd
import numpy as np

def compute_volume_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame with 'close' and 'volume', computes the 20-day volume ratio and SMAs.
    """
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
```

---

## 2. Market State Classification

Once the directional volume ratios and moving averages are computed, the engine evaluates the most recent day's data against a strict hierarchy of conditional checks to assign the Market State.

### The Classification Hierarchy

The algorithm evaluates states in the following order of precedence:

1. **Capitulation (Panic Selling)**
   - **Condition**: The absolute 20-day price drop is severe (worse than -10%) **AND** the current day's volume is exceptionally high (more than 2x the 20-day average volume).
   - **Rationale**: A massive price drop accompanied by enormous volume usually signifies panic selling and a potential near-term wash-out bottom.

2. **Distribution (Institutional Selling)**
   - **Condition**: The price is above its 20-day SMA (price is ostensibly rising), **BUT** the Up/Down Volume Ratio is `< 1.0`.
   - **Rationale**: The stock is holding up, but more volume is occurring on down days. This divergence suggests "smart money" is selling into strength.

3. **Accumulation (Institutional Buying)**
   - **Condition**: The price is flat or weak (Below 20-day SMA OR 20-day return is less than 2%), **BUT** the Up/Down Volume Ratio is remarkably strong (`> 1.2`).
   - **Rationale**: Despite poor price action, significantly more volume is transacting on up days, revealing underlying accumulation.

4. **Consolidation (Quiet Ranging)**
   - **Condition**: The distance between the 20-day high and 20-day low is extremely tight (less than 5% of the current price) **AND** current volume is below the 20-day average.
   - **Rationale**: The stock is chopping sideways on low volume, indicating exhaustion of both buyers and sellers while waiting for a catalyst.

5. **Neutral**
   - **Condition**: None of the above conditions apply.
   - **Rationale**: The market is behaving ordinarily without extreme volume/price divergences.

### Code Example: Classification Logic
```python
def classify_market_state(row: pd.Series) -> str:
    """
    Evaluates a single day's computed metrics to determine the Market Regime.
    """
    current_price = row["close"]
    current_volume = row["volume"]
    volume_mean_20d = row["vol_mean_20d"]
    price_change_20d = row["price_change_20d"]
    current_ratio = row["ud_vol_ratio"]
    sma20 = row["sma20"]
    
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
        high_20 = row["high_20d"]
        low_20 = row["low_20d"]
        range_pct = (high_20 - low_20) / current_price
        
        if range_pct < 0.05 and current_volume < volume_mean_20d:
             return "Consolidation"
             
    # 5. Default
    return "Neutral"
```

## Summary Interpretation
* The core premise relies on **volume divergences**. 
* High ratios during downtrends (`Accumulation`) or low ratios during uptrends (`Distribution`) are the most powerful signals generated by this script.
* A ratio of `1.0` acts as the centerline, with deviations naturally capturing the dominant intraday flow.
