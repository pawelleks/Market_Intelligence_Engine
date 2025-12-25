
import pandas as pd
import numpy as np
from pathlib import Path
from mie_lib.utils.paths import RAW_DIR
from mie_lib.utils.logging import get_logger

LOG = get_logger("analytics.volume_regime")

def _load_raw_data(ticker: str) -> pd.DataFrame:
    """Load raw OHLCV data for a ticker using standardization from build_features."""
    p_parquet = RAW_DIR / f"{ticker}.parquet"
    p_csv = RAW_DIR / f"{ticker}.csv"
    
    # Fallback to repo-relative raw dir if needed
    alt_raw_dir = Path("data") / "raw"
    p_parquet_alt = alt_raw_dir / f"{ticker}.parquet"
    p_csv_alt = alt_raw_dir / f"{ticker}.csv"

    if p_parquet.exists():
        df = pd.read_parquet(p_parquet)
    elif p_csv.exists():
        df = pd.read_csv(p_csv)
    elif p_parquet_alt.exists():
        df = pd.read_parquet(p_parquet_alt)
    elif p_csv_alt.exists():
        df = pd.read_csv(p_csv_alt)
    else:
        raise FileNotFoundError(f"Raw file not found for {ticker}")

    if "date" not in df.columns:
        df = df.reset_index()
    
    # Ensure date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    
    df["date"] = df["date"].dt.tz_localize(None)
    df = df.sort_values(by="date").reset_index(drop=True)
    return df

def calculate_volume_regime(ticker: str, data: pd.DataFrame = None) -> dict:
    """
    Calculates Volume Regime metrics for a given stock.
    
    Args:
        ticker: Stock ticker symbol.
        data: Optional DataFrame. If None, loads from raw storage.
        
    Returns:
        Dictionary containing:
        - current_ratio: Up/Down Volume Ratio (20-day)
        - market_state: "Distribution", "Accumulation", "Capitulation", "Consolidation", "Neutral"
        - volume_mean_20d: Average volume last 20 days
        - current_volume: Most recent volume
        - price_change_20d: % change over last 20 days
    """
    try:
        if data is None:
            df = _load_raw_data(ticker)
        else:
            df = data.copy()
            
        if df.empty or len(df) < 20:
             return {
                "ticker": ticker,
                "current_ratio": None,
                "market_state": "Insufficient Data",
                "volume_mean_20d": None,
                "current_volume": None,
                "price_change_20d": None,
                "current_price": None
            }

        if "date" not in df.columns:
             df = df.reset_index()
        df = df.sort_values("date").reset_index(drop=True)

        # 1. Prepare Price and Close/Prev Close
        # Prefer adj_close, fallback to close
        price_col = "adj_close" if "adj_close" in df.columns else "close"
        
        # Calculate daily price change to determine Green/Red days (Close > Prev Close)
        # Note: Valid methods include Close > Open or Close > Prev Close. 
        # For Volume Flow/OBV analysis, Close > Prev Close is standard.
        # We will use Close > Prev Close as "Green Day".
        df["prev_close"] = df[price_col].shift(1)
        df["price_change"] = df[price_col] - df["prev_close"]
        
        # 2. Calculate Up/Down Volume Components
        # Up Volume: Volume where price_change > 0
        # Down Volume: Volume where price_change < 0
        # Neutral Volume: Volume where price_change == 0 (ignored or split? usually ignored in simple ratio)
        
        df["up_vol"] = np.where(df["price_change"] > 0, df["volume"], 0)
        df["down_vol"] = np.where(df["price_change"] < 0, df["volume"], 0)
        
        # 3. Rolling 20-day Sums
        df["roll_up_vol"] = df["up_vol"].rolling(window=20).sum()
        df["roll_down_vol"] = df["down_vol"].rolling(window=20).sum()
        
        # Avoid division by zero
        df["ud_vol_ratio"] = np.where(df["roll_down_vol"] == 0, 
                                      np.where(df["roll_up_vol"] > 0, 100.0, 1.0), # If down is 0, if up > 0 ratio is huge
                                      df["roll_up_vol"] / df["roll_down_vol"])

        # 4. Metrics for Classification
        current_idx = df.index[-1]
        current_row = df.iloc[-1]
        
        current_ratio = float(current_row["ud_vol_ratio"])
        current_price = current_row[price_col]
        current_volume = float(current_row["volume"])
        
        # 20-day Price Change %
        price_20d_ago = df.iloc[-20][price_col] if len(df) >= 20 else df.iloc[0][price_col]
        price_change_20d = (current_price - price_20d_ago) / price_20d_ago
        
        # 20-day Avg Volume
        volume_mean_20d = df["volume"].rolling(window=20).mean().iloc[-1]
        
        # Price Trend (SMA5 vs SMA20)
        sma5 = df[price_col].rolling(window=5).mean().iloc[-1]
        sma20 = df[price_col].rolling(window=20).mean().iloc[-1]
        
        # 5. Market State Classification
        # - "Distribution" (Price rising, but Up/Down Volume Ratio < 1.0)
        # - "Accumulation" (Price flat/down, but Up/Down Volume Ratio > 1.2)
        # - "Capitulation" (Price down > 10%, Volume > 2x average)
        # - "Consolidation" (Price range tight, Volume declining)
        # - "Neutral" (Default)
        
        state = "Neutral"
        
        # Capitulation check (Severe drop + High Volume)
        if price_change_20d < -0.10 and current_volume > (2 * volume_mean_20d):
            state = "Capitulation"
            
        # Distribution check (Price Rising + Weak Volume Ratio)
        # Price Rising: SMA5 > SMA20 or Price > SMA20
        elif (current_price > sma20) and (current_ratio < 1.0):
            state = "Distribution"
            
        # Accumulation check (Price Flat/Down + Strong Volume Ratio)
        # Price Flat/Down: Price < SMA20 or Price Change 20d < 0.02 (approx flat/bearish)
        # Ratio > 1.2
        elif (current_price <= sma20 or price_change_20d < 0.02) and (current_ratio > 1.2):
            state = "Accumulation"
            
        # Consolidation check (Tight Range + Declining Volume)
        # Tight Range: Std Dev of last 20d returns is low? Or just High/Low range.
        # Declining Volume: Current Vol < Avg Vol * 0.8?
        # Let's use: (High20 - Low20)/Current < 0.05 (5% range) AND Volume < Avg
        else:
            # Check Consolidation
            high_20 = df[price_col].rolling(window=20).max().iloc[-1]
            low_20 = df[price_col].rolling(window=20).min().iloc[-1]
            range_pct = (high_20 - low_20) / current_price
            
            if range_pct < 0.05 and current_volume < volume_mean_20d:
                 state = "Consolidation"

        return {
            "ticker": ticker,
            "current_price": round(float(current_price), 2),
            "current_ratio": round(current_ratio, 3),
            "market_state": state,
            "volume_mean_20d": round(volume_mean_20d, 0),
            "current_volume": round(current_volume, 0),
            "price_change_20d": round(price_change_20d, 4),
            "last_date": str(current_row["date"].date()),
            "rel_vol_20": round(current_volume / volume_mean_20d, 2) if volume_mean_20d > 0 else 0,
            "buy_pressure_ratio": round(current_ratio, 2)
        }

    except Exception as e:
        LOG.error(f"Failed to calculate volume regime for {ticker}: {e}")
        return {
            "ticker": ticker,
            "error": str(e)
        }

def generate_volume_conclusion(metrics: dict) -> str:
    """
    Generates a natural language conclusion based on volume metrics.
    """
    if "error" in metrics or metrics.get("market_state") == "Insufficient Data":
        return "⚠️ Data Insufficient: Unable to analyze volume regime."
        
    state = metrics.get("market_state", "Neutral")
    ticker = metrics.get("ticker", "Stock")
    ratio = metrics.get("current_ratio", 0.0)
    
    if state == "Distribution":
        return f"⚠️ Warning: {ticker} is rising, but volume is higher on down days (Distribution). Up/Down Ratio: {ratio}."
    
    elif state == "Accumulation":
        return f"✅ Bullish: {ticker} is showing strength. Buying volume is dominant despite price action (Accumulation). Ratio: {ratio}."
        
    elif state == "Capitulation":
        return f"🛑 Danger: Heavy volume selling detected. Potential capitulation in {ticker}."
        
    elif state == "Consolidation":
        return f"✅ Bullish: {ticker} is consolidating with drying volume. Sellers appear exhausted."
        
    else:
        # Neutral
        if ratio > 1.0:
            return f"ℹ️ Neutral: {ticker} volume flow is slightly positive (Ratio: {ratio})."
        else:
            return f"ℹ️ Neutral: {ticker} volume flow is balanced to slightly negative (Ratio: {ratio})."

def calculate_and_save_volume_regime():
    """
    Calculates Volume Regime metrics for all tickers and saves daily snapshot.
    """
    from mie_lib.data_ingest.yfinance_loader import read_tickers
    from mie_lib.utils.paths import DATA_DIR
    
    ANALYTICS_DIR = DATA_DIR / "analytics"
    
    tickers = read_tickers()
    results = []
    
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    LOG.info(f"Starting Volume Regime Analysis for {len(tickers)} tickers...")
    
    score_map = {
        "Accumulation": 9,
        "Consolidation": 7,
        "Neutral": 5,
        "Distribution": 3,
        "Capitulation": 1,
        "Insufficient Data": 0
    }
    
    for ticker in tickers:
        ticker = ticker.strip().upper()
        try:
            metrics = calculate_volume_regime(ticker)
            if "error" in metrics:
                continue
                
            state = metrics.get("market_state", "Neutral")
            
            # Map keys to LLM payload expectations
            # "volume_regime": market_state
            # "relative_volume_10d": rel_vol_20 (using 20d as proxy or re-calc)
            # "volume_trend_score": mapped from state
            # "buying_pressure_ratio": current_ratio
            
            results.append({
                "ticker": ticker,
                "date": metrics.get("last_date"),
                "volume_regime": state,
                "rel_vol_10": metrics.get("rel_vol_20"), # Using 20d as proxy
                "vol_trend_score": score_map.get(state, 5),
                "buy_pressure_ratio": metrics.get("buy_pressure_ratio")
            })
            
        except Exception as e:
            LOG.error(f"Error processing Volume Regime for {ticker}: {e}")
            
    if results:
        df_out = pd.DataFrame(results)
        out_path = ANALYTICS_DIR / "volume_daily.parquet"
        df_out.to_parquet(out_path, index=False)
        LOG.info(f"Saved Volume Regime data to {out_path} ({len(df_out)} records)")
    else:
        LOG.warning("No Volume Regime results generated.")

if __name__ == "__main__":
    # Test block
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    print(f"Calculating Volume Regime for {ticker}...")
    result = calculate_volume_regime(ticker)
    conclusion = generate_volume_conclusion(result)
    result["conclusion"] = conclusion
    print(result)
