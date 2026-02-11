"""
Ingest 1 year of EOD history from Theta Terminal REST API.
Saves Parquet files to data/history/{TICKER}.parquet for use by the FastAPI endpoint.
"""
import httpx
import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path

# --- CONFIG ---
THETA_URL = "http://theta_terminal:25510"
TICKERS = ['SPX', 'SPY', 'QQQ', 'IWM']
OUTPUT_DIR = Path('/app/data/history')
LOOKBACK_DAYS = 730


def fetch_stock_eod(client: httpx.Client, root: str, start: str, end: str) -> pd.DataFrame:
    """Fetch EOD candles for a stock/ETF via /v2/hist/stock/eod."""
    url = f"{THETA_URL}/v2/hist/stock/eod"
    params = {"root": root, "start_date": start, "end_date": end}
    resp = client.get(url, params=params, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, dict) or "response" not in data:
        return pd.DataFrame()

    header = data.get("header", {}).get("format", [])
    rows = data["response"]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=header)
    return df


def fetch_index_price(client: httpx.Client, root: str, start: str, end: str) -> pd.DataFrame:
    """Fetch hourly index prices and resample to daily OHLC via /v2/hist/index/price."""
    url = f"{THETA_URL}/v2/hist/index/price"
    params = {
        "root": root,
        "start_date": start,
        "end_date": end,
        "ivl": "3600000",  # 1-hour buckets
    }
    resp = client.get(url, params=params, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, dict) or "response" not in data:
        return pd.DataFrame()

    header = data.get("header", {}).get("format", [])
    rows = data["response"]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=header)

    # Parse the date column (YYYYMMDD int) and price
    if "date" not in df.columns or "price" not in df.columns:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df[df["price"] > 0]

    # Resample hourly ticks to daily OHLC
    daily = df.groupby(df["date"].dt.date)["price"].agg(
        open="first", high="max", low="min", close="last"
    ).reset_index()
    daily.rename(columns={"date": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"])
    daily["volume"] = 0  # Indices don't have volume
    return daily


def sanitize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Fix bad ticks using rolling median comparison.
    If a bar's low/high deviates > 10% from 5-bar rolling median, replace with median."""
    if df.empty or "low" not in df.columns or "high" not in df.columns:
        return df
    for col in ["low", "high"]:
        med = df[col].rolling(5, center=True, min_periods=1).median()
        pct_dev = (df[col] - med).abs() / med
        bad = pct_dev > 0.10
        if bad.any():
            tickers = df["date"].dt.strftime("%Y-%m-%d") if "date" in df.columns else df.index
            for idx in df.index[bad]:
                print(f"   > SANITIZE: {col} on {tickers[idx]}: {df.at[idx, col]:.2f} -> {med[idx]:.2f}")
            df.loc[bad, col] = med[bad]
    return df


def normalize_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a stock EOD DataFrame to standard columns."""
    cols = [c.lower() for c in df.columns]
    df.columns = cols

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d", errors="coerce")

    # Keep only the standard OHLCV columns
    keep = ["date", "open", "high", "low", "close", "volume"]
    available = [c for c in keep if c in df.columns]
    df = df[available].copy()

    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

    df = df.dropna(subset=["date", "close"])
    df = df.sort_values("date").reset_index(drop=True)

    # Sanitize bad ticks
    df = sanitize_ohlc(df)
    return df


def main():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    fmt_start = start_date.strftime("%Y%m%d")
    fmt_end = end_date.strftime("%Y%m%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f">>> Ingesting {LOOKBACK_DAYS} days of history ({fmt_start} -> {fmt_end})")

    with httpx.Client() as client:
        for root in TICKERS:
            print(f"--- {root} ---")
            try:
                if root in ["SPX", "VIX"]:
                    df = fetch_index_price(client, root, fmt_start, fmt_end)
                    df = sanitize_ohlc(df)
                else:
                    df = fetch_stock_eod(client, root, fmt_start, fmt_end)
                    df = normalize_stock_df(df)

                if df.empty:
                    print(f"   > WARNING: No data for {root}")
                    continue

                out_path = OUTPUT_DIR / f"{root}.parquet"
                df.to_parquet(out_path, index=False)
                print(f"   > Saved {len(df)} rows -> {out_path}")

            except Exception as e:
                print(f"   > ERROR: {e}")

    print(">>> DONE: History ingestion complete.")


if __name__ == "__main__":
    main()
