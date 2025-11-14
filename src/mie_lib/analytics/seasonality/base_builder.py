"""
Seasonality base builder helpers.

This module generates a per-ticker base parquet used by the Seasonality Analysis page.
It reuses existing OFFLINE artifacts only (raw + features), performs no network IO,
and writes outputs atomically per ARCHITECT_BIBLE.

Outputs (one per ticker):
  data/seasonality/base/{TICKER}.parquet
Schema (minimum required by the page):
  - ticker (str)
  - date (datetime64[ns, UTC] recommended)
  - year (int)
  - doy_trading (int, 1..N within calendar year)
  - open, high, low, close (floats; from raw if available)
  - r  (simple daily return in decimal, based on adj_close if present else close)
  - lr (log daily return in decimal)
  - month (1..12)
  - day (1..31)

This file is authoritative for seasonality views; heavier facts/aggregations can be
precomputed elsewhere. This base is lightweight and idempotent.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List

import pandas as pd
import numpy as np

from mie_lib.utils.logging import get_logger
from mie_lib.utils.paths import RAW_DIR, seasonality_base_path

LOG = get_logger("seasonality.base")


def get_seasonality_universe() -> List[str]:
    """Resolve the analytics universe for seasonality.
    Prefer the same tickers used by other analytics by reading config via existing
    ingest helper. Falls back to empty list on error.
    """
    try:
        from mie_lib.data_ingest.yfinance_loader import read_tickers
        tickers = [t.strip().upper() for t in read_tickers() if str(t).strip()]
        return sorted(set(tickers))
    except Exception as e:  # pragma: no cover
        LOG.warning("get_seasonality_universe: failed to load tickers: %s", e)
        return []


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    # fsync temp file for durability
    with open(tmp, "rb") as f:
        import os
        os.fsync(f.fileno())
    # atomic replace
    import os as _os
    _os.replace(tmp, path)
    return path


def _load_raw_ohlc(ticker: str) -> pd.DataFrame | None:
    p = RAW_DIR / f"{ticker}.parquet"
    if not p.exists():
        # allow CSV fallback
        p_csv = RAW_DIR / f"{ticker}.csv"
        if not p_csv.exists():
            return None
        try:
            df = pd.read_csv(p_csv)
        except Exception:
            return None
    else:
        try:
            df = pd.read_parquet(p)
        except Exception:
            return None
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])  # make naive first
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    # Ensure canonical columns exist
    for col in ["open", "high", "low", "close", "adj_close", "ticker"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "ticker" not in df.columns:
        df["ticker"] = ticker
    return df


def _ensure_returns_from_prices(df_prices: pd.DataFrame) -> pd.DataFrame:
    """Compute simple and log returns from adj_close if present else close.
    Returns a copy with columns r and lr added.
    """
    px = df_prices.copy()
    # choose adj_close preferred; else close
    if "adj_close" in px.columns and px["adj_close"].notna().any():
        base = pd.to_numeric(px["adj_close"], errors="coerce")
    else:
        base = pd.to_numeric(px["close"], errors="coerce")
    r = base.pct_change()
    # Avoid log of non-positive
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.log(base / base.shift(1))
    px["r"] = r
    px["lr"] = lr
    return px


def build_seasonality_base_for_ticker(ticker: str, cfg: Dict) -> Dict[str, object]:
    """Build seasonality base parquet for a single ticker from existing RAW/FEATURES.

    cfg keys (optional):
      - force (bool): overwrite even if output exists
      - min_years (int): minimum years required to consider base meaningful (informational)
      - return_type (str): 'log' or 'simple' (base stores both r and lr regardless)
      - lookbacks (list): kept for compatibility; not used directly in base build
    """
    t = ticker.strip().upper()
    force = bool(cfg.get("force", True))
    out_path = seasonality_base_path(t)

    if out_path.exists() and not force:
        LOG.info("seasonality base exists for %s; skip (use --force to rebuild)", t)
        try:
            df = pd.read_parquet(out_path)
            rows = len(df)
            dmin = str(pd.to_datetime(df["date"]).min().date()) if "date" in df.columns else "NA"
            dmax = str(pd.to_datetime(df["date"]).max().date()) if "date" in df.columns else "NA"
        except Exception:
            rows, dmin, dmax = 0, "NA", "NA"
        return {"ticker": t, "status": "ok", "rows": rows, "min": dmin, "max": dmax, "path": str(out_path)}

    # Load RAW for OHLC and to compute returns
    raw = _load_raw_ohlc(t)
    if raw is None or raw.empty:
        return {"ticker": t, "status": "skip", "reason": "no raw"}

    # Compute returns from prices
    px = _ensure_returns_from_prices(raw)

    # Build base frame with required columns
    base = px[["date", "open", "high", "low", "close", "ticker", "r", "lr"]].copy()
    # Ensure datetime timezone normalized to UTC for UI consistency
    base["date"] = pd.to_datetime(base["date"], utc=True)
    base["year"] = base["date"].dt.year.astype(int)
    # Trading-day index within calendar year (1..N) based on existing rows
    base = base.sort_values("date").reset_index(drop=True)
    base["doy_trading"] = base.groupby("year").cumcount() + 1
    base["month"] = base["date"].dt.month.astype(int)
    base["day"] = base["date"].dt.day.astype(int)

    # Drop rows where returns are NaN for both r and lr (first row of dataset per year may be NaN)
    mask_valid = base[["r", "lr"]].notna().any(axis=1)
    base = base[mask_valid].reset_index(drop=True)
    # IMPORTANT: Recompute doy_trading after filtering so each year starts at 1
    base["doy_trading"] = base.groupby("year").cumcount() + 1

    # Write atomically
    try:
        path = _atomic_write_parquet(base, out_path)
    except Exception as e:
        LOG.exception("Failed to write seasonality base for %s: %s", t, e)
        return {"ticker": t, "status": "error", "error": str(e)}

    return {
        "ticker": t,
        "status": "ok",
        "rows": int(len(base)),
        "min": str(base["date"].min().date()) if not base.empty else "NA",
        "max": str(base["date"].max().date()) if not base.empty else "NA",
        "path": str(path),
    }
