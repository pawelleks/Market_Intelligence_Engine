from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import timezone

# Canonical locations per Bible: prefer features parquet, fallback to raw
try:
    from mie_lib.features.build_features import FEATURES_DIR
except Exception:
    FEATURES_DIR = Path("data") / "features"

RAW_DIR = Path("data") / "raw"
SEAS_BASE_DIR = Path("data") / "seasonality" / "base"
SEAS_BASE_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLS_FEATURES = {"date", "ticker", "ret_1d", "adj_close", "close"}


def _load_prices_for_ticker(ticker: str) -> pd.DataFrame:
    """Load canonical price series for seasonality.
    Prefer features parquet; fallback to raw parquet/csv. Returns DataFrame with columns:
    date (UTC), ticker, close, optional ret_1d.
    """
    t = ticker.upper().strip()
    p_feat_parquet = FEATURES_DIR / f"{t}.parquet"
    p_feat_csv = FEATURES_DIR / f"{t}.csv"

    df: pd.DataFrame | None = None
    src_df: pd.DataFrame | None = None
    if p_feat_parquet.exists():
        src_df = pd.read_parquet(p_feat_parquet)
    elif p_feat_csv.exists():
        src_df = pd.read_csv(p_feat_csv)
    else:
        # fallback raw
        p_raw_parquet = RAW_DIR / f"{t}.parquet"
        p_raw_csv = RAW_DIR / f"{t}.csv"
        if p_raw_parquet.exists():
            src_df = pd.read_parquet(p_raw_parquet)
        elif p_raw_csv.exists():
            src_df = pd.read_csv(p_raw_csv)

    if src_df is None or src_df.empty:
        raise FileNotFoundError(f"No price file found for {t}")

    # Normalize columns
    if "date" not in src_df.columns:
        src_df = src_df.reset_index()
    # Coerce to UTC timezone-aware
    dt = pd.to_datetime(src_df["date"], utc=True)
    src_df["date"] = dt

    # Choose adjusted close if present, else close
    close_col = "adj_close" if "adj_close" in src_df.columns else ("Adj Close" if "Adj Close" in src_df.columns else None)
    if close_col is None:
        close_col = "close" if "close" in src_df.columns else ("Close" if "Close" in src_df.columns else None)
    if close_col is None:
        raise ValueError("close/adj_close column missing for seasonality preprocessing")

    cols = {
        "date": src_df["date"],
        "ticker": t,
        "close": pd.to_numeric(src_df[close_col], errors="coerce"),
    }
    # Pass through ret_1d from features if available for exact alignment
    if "ret_1d" in src_df.columns:
        cols["ret_1d"] = pd.to_numeric(src_df["ret_1d"], errors="coerce")

    out = pd.DataFrame(cols)

    # Drop rows with missing close and duplicates, sort by date
    out = out.dropna(subset=["close"]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return out


def build_seasonality_base(ticker: str) -> Path:
    """Build per-ticker base seasonality parquet with columns:
    ticker, date (UTC), year, doy_trading, open, high, low, close, r, lr
    Notes:
      - open/high/low are best-effort (if available from source); else set NaN.
      - r: simple return, lr: log return (float32)
    """
    df = _load_prices_for_ticker(ticker)

    # Bring OHLC if available (features may not carry OHL)
    # Attempt to re-open raw for OHL, then left-join on date
    try:
        p_raw_parquet = RAW_DIR / f"{ticker.upper()}.parquet"
        if p_raw_parquet.exists():
            raw = pd.read_parquet(p_raw_parquet)
        else:
            raw = None
        if raw is not None:
            if "date" not in raw.columns:
                raw = raw.reset_index()
            raw["date"] = pd.to_datetime(raw["date"], utc=True)
            cols = [c for c in ["open","high","low","close","adj_close"] if c in raw.columns]
            raw_ohlc = raw[["date", *cols]].copy()
            # prefer adjusted close for close if available
            if "adj_close" in raw_ohlc.columns:
                raw_ohlc["close"] = raw_ohlc["adj_close"]
            df = df.merge(raw_ohlc, on="date", how="left", suffixes=("", "_raw"))
            # Final close preference: df.close (features) then raw adj_close/close
            df["close"] = df["close"].fillna(df.get("adj_close")).fillna(df.get("close_raw"))
            for c in ("open","high","low"):
                if c not in df.columns:
                    df[c] = np.nan
        else:
            for c in ("open","high","low"):
                df[c] = np.nan
    except Exception:
        for c in ("open","high","low"):
            if c not in df.columns:
                df[c] = np.nan

    # Compute returns: prefer features ret_1d for exact alignment
    df = df.sort_values("date").reset_index(drop=True)
    if "ret_1d" in df.columns and not df["ret_1d"].isna().all():
        df["r"] = df["ret_1d"].astype("float32")
        with np.errstate(divide='ignore', invalid='ignore'):
            df["lr"] = np.log1p(df["r"]).astype("float32")
    else:
        df["r"] = df["close"].pct_change().astype("float32")
        with np.errstate(divide='ignore', invalid='ignore'):
            df["lr"] = np.log(df["close"] / df["close"].shift(1)).astype("float32")

    # Year and trading-day index within calendar year
    df["year"] = df["date"].dt.year
    df["doy_trading"] = df.groupby("year").cumcount() + 1

    # Data quality filters: drop leading NA returns where shift creates NaN
    df = df.dropna(subset=["close"])  # close must exist
    df = df.drop_duplicates(subset=["date"]).reset_index(drop=True)

    # Select final schema
    out = df[[
        "ticker", "date", "year", "doy_trading", "open", "high", "low", "close", "r", "lr"
    ]].copy()

    # Write atomically
    SEAS_BASE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SEAS_BASE_DIR / f".{ticker.upper()}.parquet.tmp"
    final = SEAS_BASE_DIR / f"{ticker.upper()}.parquet"
    out.to_parquet(tmp, index=False)
    tmp.replace(final)
    return final
