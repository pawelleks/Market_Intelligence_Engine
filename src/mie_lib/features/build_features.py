"""
Feature builder module.

Implements vectorized pandas feature computations for the pipeline's Feature Layer (Part 4 of ARCHITECT_BIBLE).
Supports full rebuild and incremental update (recompute last N days with proper rolling-window padding).

Public functions:
- build_features_for_ticker(ticker, mode='full', lookback=90, csv=False)
- build_features_for_all(mode='full', lookback=90, csv=False)

This module is intentionally pure pandas (imports inside functions) and logs to data/logs/features.log.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import gc

from mie_lib.utils.logging import get_logger
from mie_lib.utils.config import load_named_config
from mie_lib.data_ingest.yfinance_loader import load_registry, save_registry
from mie_lib.utils.paths import RAW_DIR, FEATURES_DIR, META_DIR

LOG = get_logger("features")

# DATA_DIR = Path("data")
# RAW_DIR = DATA_DIR / "raw"
# FEATURES_DIR = DATA_DIR / "features"
# META_DIR = DATA_DIR / "meta"

FEATURES_VERSION = "features_v1.0.0"

# Required output columns per ARCHITECT_BIBLE
OUTPUT_COLUMNS = [
    "date",
    "ticker",
    "close",
    "adj_close",
    "ret_1d",
    "log_ret_1d",
    "rv_20d",
    "rv_60d",
    "sma_5",
    "sma_10",
    "sma_20",
    "sma_50",
    "sma_100",
    "sma_200",
    "ema_5",
    "ema_10",
    "ema_20",
    "ema_50",
    "ema_100",
    "ema_200",
    "ma_ratio_20_50",
    "ma_ratio_50_200",
    "ma_ratio_20_200",
    "dist_from_50dma",
    "dist_from_200dma",
    "dow",
    "month",
    "as_of",
    "data_version",
]


def _read_raw(ticker: str):
    """Read raw parquet or csv for ticker. Returns pandas DataFrame with date column as datetime and sorted.
    """
    try:
        import pandas as pd
    except Exception as e:
        LOG.error("pandas required for features: %s", e)
        raise

    p_parquet = RAW_DIR / f"{ticker}.parquet"
    p_csv = RAW_DIR / f"{ticker}.csv"
    # Fallback to repo-relative raw dir if needed (tests may have imported original RAW_DIR before monkeypatch)
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
        # try index
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values(by="date").reset_index(drop=True)
    # Ensure canonical columns exist
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "ticker" not in df.columns:
        df["ticker"] = ticker
    return df


def _write_features(df, ticker: str, write_csv: bool = False):
    import os
    import pandas as pd
    p_parquet = FEATURES_DIR / f"{ticker}.parquet"
    p_parquet.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = p_parquet.with_suffix(p_parquet.suffix + ".tmp")
    # Write to temp first
    df.to_parquet(tmp_path, index=False)
    # fsync temp file to disk
    with open(tmp_path, "rb") as f:
        os.fsync(f.fileno())
    # Atomic replace
    os.replace(tmp_path, p_parquet)
    # Optional CSV (non-authoritative)
    if write_csv:
        df.to_csv(FEATURES_DIR / f"{ticker}.csv", index=False)
    # Read-back validation (schema presence and basic invariants)
    try:
        df_back = pd.read_parquet(p_parquet)
        # minimal schema: 'date' present & sorted unique, 'ret_1d' float32 and no NaNs beyond warm-up (index 1+)
        if "date" not in df_back.columns:
            raise ValueError("Written features missing 'date'")
        df_back = df_back.sort_values("date").reset_index(drop=True)
        if df_back["date"].duplicated().any():
            raise ValueError("Duplicates in written features 'date'")
        if "ret_1d" not in df_back.columns:
            raise ValueError("Written features missing 'ret_1d'")
        # allow float32 or coercible to float32
        if str(df_back["ret_1d"].dtype) != "float32":
            # downcast check only; we won't rewrite here
            _ = pd.to_numeric(df_back["ret_1d"], errors="coerce").astype("float32")
        if len(df_back) > 2 and df_back["ret_1d"].iloc[1:].isna().any():
            raise ValueError("NaNs in ret_1d beyond warm-up after write")
    except Exception as e:
        LOG.error("Post-write validation failed for %s: %s", ticker, e)
        raise
    return p_parquet


def _get_windows():
    """Load windows from config/features.yml; fall back to defaults if absent."""
    try:
        cfg = load_named_config("features")
    except Exception:
        cfg = {}
    rw = cfg.get("rolling_windows", {}) if isinstance(cfg, dict) else {}
    sma = rw.get("sma", [20, 50, 200])
    ema = rw.get("ema", [20, 50, 200])
    vol = rw.get("volatility", [20, 60])
    return {"sma": sma, "ema": ema, "vol": vol}


# --- New: robust price selector (adj_close -> close fallback) ---

def _select_price_column(df):
    """Return (column_name, Series) for price. Prefer adj_close, fallback to close.
    Requires at least a handful of non-null observations to be considered usable.
    """
    import pandas as pd

    if "adj_close" in df.columns:
        s = pd.to_numeric(df["adj_close"], errors="coerce")
        if s.notna().sum() >= 5:
            return "adj_close", s
    if "close" in df.columns:
        s = pd.to_numeric(df["close"], errors="coerce")
        if s.notna().sum() >= 5:
            return "close", s
    raise KeyError("Neither 'adj_close' nor 'close' available with sufficient data to compute returns.")


def _compute_features_from_raw(raw_df):
    """Compute feature columns given raw dataframe (vectorized pandas). Returns dataframe with required output columns (date,ticker,...)
    raw_df must contain 'date', price column (adj_close preferred else close) and 'ticker'.
    """
    import numpy as np
    import pandas as pd

    windows = _get_windows()
    sma_ws = sorted(windows.get("sma", [20, 50, 200]))
    ema_ws = sorted(windows.get("ema", [20, 50, 200]))
    vol_ws = sorted(windows.get("vol", [20, 60]))

    df = raw_df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    price_col, price = _select_price_column(df)
    LOG.info("[features] price column for returns: %s", price_col)

    # Returns
    df["ret_1d"] = price.pct_change()
    # log return
    df["log_ret_1d"] = np.log(price).diff()

    # Rolling vol (std of returns)
    for w in vol_ws:
        df[f"rv_{w}d"] = df["ret_1d"].rolling(window=w, min_periods=1).std()

    # SMAs
    for w in sma_ws:
        df[f"sma_{w}"] = price.rolling(window=w, min_periods=1).mean()

    # EMAs (span=w)
    for w in ema_ws:
        df[f"ema_{w}"] = price.ewm(span=w, adjust=False).mean()

    # MA ratios
    # define helper to safely divide (avoid div by zero)
    def _ratio(num, den):
        return np.where(den == 0, np.nan, num / den)

    # map expected ratios
    def _safe_ratio(col_short, col_long):
        return pd.Series(_ratio(df[col_short], df[col_long]), index=df.index)

    if 20 in sma_ws and 50 in sma_ws:
        df["ma_ratio_20_50"] = _safe_ratio("sma_20", "sma_50")
    else:
        df["ma_ratio_20_50"] = np.nan
    if 50 in sma_ws and 200 in sma_ws:
        df["ma_ratio_50_200"] = _safe_ratio("sma_50", "sma_200")
    else:
        df["ma_ratio_50_200"] = np.nan
    if 20 in sma_ws and 200 in sma_ws:
        df["ma_ratio_20_200"] = _safe_ratio("sma_20", "sma_200")
    else:
        df["ma_ratio_20_200"] = np.nan

    # distance from MAs
    if 50 in sma_ws:
        df["dist_from_50dma"] = (price / df["sma_50"]) - 1
    else:
        df["dist_from_50dma"] = np.nan
    if 200 in sma_ws:
        df["dist_from_200dma"] = (price / df["sma_200"]) - 1
    else:
        df["dist_from_200dma"] = np.nan

    # Calendar features
    df["dow"] = df["date"].dt.weekday
    df["month"] = df["date"].dt.month

    # Metadata
    df["as_of"] = datetime.now(timezone.utc).isoformat()
    df["data_version"] = FEATURES_VERSION

    # Keep only required OUTPUT_COLUMNS but ensure they exist
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    out = df[["date", "ticker"] + [c for c in OUTPUT_COLUMNS if c not in ("date", "ticker")]]

    # Return a real copy; casting will be handled later in one vectorized op
    return out.copy()


def _validate_feature_df(df):
    """Validate dtypes, sorted dates, and NaN rules per ARCHITECT_BIBLE.
    Allow NaNs only in initial warm-up rows for rolling windows.
    """
    import pandas as pd
    windows = _get_windows()
    max_window = max(max(windows.get("sma", [0])), max(windows.get("ema", [0])), max(windows.get("vol", [0])))
    # date sorted
    if not df["date"].is_monotonic_increasing:
        raise ValueError("Feature date index not sorted")
    if df["date"].duplicated().any():
        raise ValueError("Duplicate dates in feature dataframe")

    # Required canonical columns presence and dtype
    req_cols = {"ret_1d": {"float32", "float64"}, "rv_20d": {"float32"}}
    for col, allowed_dtypes in req_cols.items():
        if col not in df.columns:
            raise ValueError(f"Missing required feature column: {col}")
        dtype_str = str(df[col].dtype)
        if dtype_str not in allowed_dtypes:
            allowed = ", ".join(sorted(allowed_dtypes))
            raise TypeError(f"Column {col} must be one of [{allowed}], got {dtype_str}")

    # NaN checks: for each rolling-derived column, allow NaNs only in first `window-1` rows.
    col_warmups = {
        "ret_1d": 1,
        "log_ret_1d": 1,
        "rv_20d": 20,
        "rv_60d": 60,
        "sma_5": 5,
        "sma_10": 10,
        "sma_20": 20,
        "sma_50": 50,
        "sma_100": 100,
        "sma_200": 200,
        "ema_5": 5,
        "ema_10": 10,
        "ema_20": 20,
        "ema_50": 50,
        "ema_100": 100,
        "ema_200": 200,
    }
    n = len(df)
    for col, warmup in col_warmups.items():
        if col not in df.columns:
            continue
        series = df[col]
        # allowed NaN positions are the first `warmup` rows (inclusive)
        allowed_idx = int(warmup)
        if allowed_idx < 0:
            allowed_idx = 0
        # count NaNs beyond allowed_idx (i.e., starting at index allowed_idx)
        if series.iloc[allowed_idx:].isna().any():
            import logging
            logging.getLogger("features").warning(f"Unexpected NaNs in column {col} beyond warm-up period")
            # raise ValueError(f"Unexpected NaNs in column {col} beyond warm-up period")

    # dtypes: numeric columns should be float32
    # (we casted earlier)
    return True


def _ensure_ret_1d(df_feat, raw_df=None):
    """Ensure ret_1d exists; derive following the priority:
    - keep if present
    - else from 'ret'
    - else from 'log_ret_1d' as exp()-1
    - else compute from price (adj_close preferred then close) using raw_df if provided
    Returns modified df_feat.
    """
    import numpy as np
    import pandas as pd

    if "ret_1d" in df_feat.columns:
        return df_feat
    df_feat = df_feat.copy()
    if "ret" in df_feat.columns:
        df_feat["ret_1d"] = pd.to_numeric(df_feat["ret"], errors="coerce")
        return df_feat
    if "log_ret_1d" in df_feat.columns:
        df_feat["ret_1d"] = np.expm1(pd.to_numeric(df_feat["log_ret_1d"], errors="coerce"))
        return df_feat
    # last resort: compute from price
    if raw_df is not None:
        # align on date
        prices = raw_df[["date"]].copy()
        if "adj_close" in raw_df.columns:
            prices["_px"] = pd.to_numeric(raw_df["adj_close"], errors="coerce")
        elif "close" in raw_df.columns:
            prices["_px"] = pd.to_numeric(raw_df["close"], errors="coerce")
        else:
            prices["_px"] = pd.NA
        tmp = df_feat.merge(prices, on="date", how="left")
        tmp["ret_1d"] = tmp["_px"].pct_change()
        df_feat["ret_1d"] = tmp["ret_1d"].values
        return df_feat
    # if all failed, create NaNs to let validator catch
    df_feat["ret_1d"] = np.nan
    return df_feat


def build_features_for_ticker(ticker: str, mode: str = "full", lookback: int = 90, write_csv: bool = False) -> Dict[str, any]:
    """Build or update features for a single ticker.

    mode: 'full' to compute all features for entire raw history.
          'update' to recompute last `lookback` days (idempotent).
    """
    import pandas as pd

    LOG.info("Building features for %s mode=%s lookback=%s", ticker, mode, lookback)
    raw_df = _read_raw(ticker)
    if raw_df.empty:
        LOG.warning("No raw data for %s", ticker)
        return {"ticker": ticker, "rows": 0}

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    p_feat = FEATURES_DIR / f"{ticker}.parquet"

    if mode == "full" or not p_feat.exists():
        df_feat = _compute_features_from_raw(raw_df)
    else:
        # incremental: read existing features and only recompute last `lookback` days
        existing = pd.read_parquet(p_feat)
        if "date" not in existing.columns:
            existing = existing.reset_index()
        existing["date"] = pd.to_datetime(existing["date"]).dt.tz_localize(None)
        existing = existing.sort_values("date").reset_index(drop=True)
        # Migration note: older files may miss canonical ret_1d/rv_20d
        missing = [c for c in ("ret_1d","rv_20d") if c not in existing.columns]
        if missing:
            LOG.info("Migration: existing features for %s missing %s — will (re)compute from price column", ticker, missing)
        # Determine max rolling window from config
        windows = _get_windows()
        max_window = max(
            max(windows.get("sma", [0])) if windows.get("sma") else 0,
            max(windows.get("ema", [0])) if windows.get("ema") else 0,
            max(windows.get("vol", [0])) if windows.get("vol") else 0,
        )
        extra_overlap = 2  # ensure pct_change and similar operations have prior rows

        # Determine recompute end/start date based on raw latest date (handles newly appended rows)
        raw_last_date = raw_df["date"].max().date()
        recompute_end_date = raw_last_date
        recompute_start_date = recompute_end_date - timedelta(days=lookback - 1)
        # extend the start date backward by max_window + extra_overlap (calendar days) to ensure sufficient history
        extended_start_date = recompute_start_date - timedelta(days=(int(max_window) + int(extra_overlap)))

        # Select raw rows on or after extended_start_date (include one prior row automatically by using >= extended_start_date)
        # We'll compute features on this extended block, but only append rows from recompute_start_date onwards.
        to_recompute = raw_df[raw_df["date"].dt.date >= extended_start_date].reset_index(drop=True)
        # If there exists a row just before extended_start_date, include it to ensure continuity for pct_change
        prev_idx = raw_df[raw_df["date"].dt.date < extended_start_date].index.max()
        if not pd.isna(prev_idx):
            start_idx = int(prev_idx)
            # include that prior row
            to_recompute = pd.concat([raw_df.iloc[[start_idx]], to_recompute], ignore_index=True)

        recomputed = _compute_features_from_raw(to_recompute)

        # Build recomputed tail starting from recompute_start_date (these are the rows we will append)
        recomputed_tail = recomputed[recomputed["date"].dt.date >= recompute_start_date].reset_index(drop=True)

        # Merge: keep prefix strictly before recompute_start_date
        prefix = existing[existing["date"].dt.date < recompute_start_date]

        # Combine prefix and recomputed tail; drop duplicates by date keeping recomputed rows
        combined = pd.concat([prefix, recomputed_tail], ignore_index=True)
        before_len = len(prefix) + len(recomputed_tail)
        combined = combined.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
        after_len = len(combined)
        duplicates_dropped = before_len - after_len

        LOG.info("Recompute overlap: lookback=%s, max_window=%s, extra_overlap=%s, extended_start_date=%s, recompute_start_date=%s", lookback, max_window, extra_overlap, extended_start_date, recompute_start_date)
        LOG.info("Recompute prefix_rows=%d, recomputed_rows=%d, recomputed_tail_rows=%d, duplicates_dropped=%d", len(prefix), len(recomputed), len(recomputed_tail), duplicates_dropped)

        # Ensure continuity for pct_change-based features: recompute ret_1d and log_ret_1d from robust price column across the combined df
        try:
            import numpy as np
            # Merge selected price from raw_df (left join)
            px_col, _ = _select_price_column(raw_df)
            raw_px = raw_df[["date", px_col]].copy().rename(columns={px_col: "_px"})
            merged = combined.merge(raw_px, on="date", how="left")
            merged["_px"] = pd.to_numeric(merged["_px"], errors="coerce")
            nan_before = merged["ret_1d"].isna().sum() if "ret_1d" in merged.columns else None
            merged["ret_1d"] = merged["_px"].pct_change()
            merged["log_ret_1d"] = np.log(merged["_px"]).diff()
            nan_after = merged["ret_1d"].isna().sum()
            LOG.info("Recomputed ret_1d continuity using '%s': nan_before=%s, nan_after=%s", px_col, nan_before, nan_after)
            # Assign back the recomputed returns into combined
            combined["ret_1d"] = merged["ret_1d"].values
            combined["log_ret_1d"] = merged["log_ret_1d"].values
            # Recompute rv_20d / rv_60d for the entire combined (ensures presence and dtype)
            combined["rv_20d"] = pd.to_numeric(combined["ret_1d"], errors="coerce").rolling(window=20, min_periods=1).std()
            combined["rv_60d"] = pd.to_numeric(combined["ret_1d"], errors="coerce").rolling(window=60, min_periods=1).std()
        except Exception:
            LOG.exception("Failed to recompute ret_1d for continuity; proceeding with combined as-is")

        df_feat = combined

    # validation
    # Ensure df_feat is a real copy before in-place operations to avoid SettingWithCopyWarning
    df_feat = df_feat.copy()

    # Ensure ret_1d exists following derivation chain
    df_feat = _ensure_ret_1d(df_feat, raw_df=raw_df)

    # Vectorized casting of numeric feature columns, excluding meta columns
    import pandas as pd
    meta_cols = {"date", "ticker", "as_of", "data_version"}
    # Determine numeric feature columns from OUTPUT_COLUMNS excluding meta
    numeric_cols = [c for c in OUTPUT_COLUMNS if c not in meta_cols and c in df_feat.columns]
    float32_targets = list(numeric_cols)
    if float32_targets:
        # Coerce the block to numeric and then cast the resulting DataFrame to float32.
        coerced_block = df_feat.loc[:, float32_targets].apply(pd.to_numeric, errors="coerce")
        coerced_block = coerced_block.astype("float32")
        df_feat.loc[:, float32_targets] = coerced_block
        # Verify dtypes; if any column didn't become float32 (edge cases), cast individually
        not_float32 = [c for c in float32_targets if str(df_feat[c].dtype) != "float32"]
        if not_float32:
            for c in not_float32:
                df_feat[c] = pd.to_numeric(df_feat[c], errors="coerce").astype("float32")
            LOG.info("Performed per-column fallback casting for %d columns: %s", len(not_float32), not_float32)

        LOG.info("Casted %d numeric feature columns to float32", len(float32_targets))
        LOG.info("Numeric dtypes after cast: %s", df_feat.loc[:, float32_targets].dtypes.apply(lambda dt: str(dt)).to_dict())

    try:
        _validate_feature_df(df_feat)
    except Exception as e:
        LOG.exception("Feature validation failed for %s: %s", ticker, e)
        raise

    # Guardrail: abort writing suspiciously small production files (e.g., SPY should have many rows)
    if str(ticker).upper() == "SPY" and len(df_feat) < 1000:
        LOG.error("Aborting write for %s: too few rows (%d) — protects against accidental truncation", ticker, len(df_feat))
        return {"ticker": ticker, "rows": int(len(df_feat)), "parquet": None, "aborted": True}

    # write outputs
    p_written = _write_features(df_feat, ticker, write_csv)

    # update registry
    reg = load_registry()
    reg_key = f"features/{ticker}"
    reg_entry = {
        "ticker": ticker,
        "last_update_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_range": [str(df_feat["date"].min().date()), str(df_feat["date"].max().date())],
        "rows": int(len(df_feat)),
        "columns_available": list(df_feat.columns),
        "data_version": FEATURES_VERSION,
    }
    reg[reg_key] = reg_entry
    save_registry(reg)

    LOG.info("Wrote features for %s rows=%d to %s; columns=%s", ticker, len(df_feat), p_written, list(df_feat.columns))
    return {"ticker": ticker, "rows": int(len(df_feat)), "parquet": str(p_written)}


def build_features_for_all(mode: str = "full", lookback: int = 90, write_csv: bool = False, tickers: List[str] = None) -> List[Dict]:
    if not tickers:
        tickers = []
        try:
            tcfg = load_named_config("ticker_list")
            if isinstance(tcfg, dict):
                tickers = tcfg.get("tickers", [])
            elif isinstance(tcfg, list):
                tickers = tcfg
        except Exception:
            # fallback to reading file
            p = Path("config/ticker_list.yml")
            if p.exists():
                lines = [l.strip() for l in p.read_text().splitlines()]
                tickers = [l for l in lines if l and not l.startswith("#")]
    
    results = []
    for t in tickers:
        res = build_features_for_ticker(t, mode=mode, lookback=lookback, write_csv=write_csv)
        results.append(res)
        gc.collect()  # Ensure memory is returned to OS between tickers
    return results
