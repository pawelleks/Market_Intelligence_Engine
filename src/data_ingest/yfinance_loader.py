"""
YFinance ingestion module.

Provides functions to:
- read tickers from config/tickers.yml
- fetch full history for a ticker and write to data/raw/{TICKER}.parquet (+ CSV fallback)
- incremental update that fetches only new rows and appends (dedupe + sort)
- validation utilities

This module follows ARCHITECT_BIBLE rules: Parquet primary, CSV fallback, never mutate raw beyond append+dedupe, logs to data/logs/, and updates data/meta/dataset_registry.json.
"""
from pathlib import Path
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from src.utils.logging import get_logger
from src.utils.config import load_named_config

LOG = get_logger("ingest")

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
META_DIR = DATA_DIR / "meta"
LOG_DIR = DATA_DIR / "logs"
REGISTRY_PATH = META_DIR / "dataset_registry.json"

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"]


def read_tickers(config_path: str = "config/tickers.yml") -> List[str]:
    """Read tickers from YAML config file. Allows simple list or top-level 'tickers' key.
    Ignores blank lines and comment lines in a fallback plain-text parsing mode.
    """
    try:
        cfg = load_named_config("tickers")
    except Exception:
        # fallback: try to read as plain text lines
        p = Path(config_path)
        if not p.exists():
            LOG.error("Tickers config not found: %s", config_path)
            return []
        lines = [l.strip() for l in p.read_text().splitlines()]
        tickers = [l for l in lines if l and not l.startswith("#")]
        return tickers

    if isinstance(cfg, dict):
        # support config with top-level 'tickers' key
        val = cfg.get("tickers") or cfg.get("symbols")
        if isinstance(val, list):
            return [t.strip() for t in val if t and isinstance(t, str)]
    if isinstance(cfg, list):
        return [t.strip() for t in cfg if t and isinstance(t, str)]
    return []


def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_registry() -> Dict[str, Dict]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text())
    except Exception:
        LOG.exception("Failed to load registry, recreating")
        return {}


def save_registry(reg: Dict[str, Dict]):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, default=str))


def _df_from_yfinance(ticker: str, start: Optional[str] = None):
    """Fetch history from yfinance. Returns a pandas DataFrame with index as DatetimeIndex and columns matching Yahoo returned fields.
    Import pandas and yfinance lazily.
    """
    try:
        import pandas as pd
    except Exception as e:
        LOG.error("pandas is required for ingestion: %s", e)
        raise
    try:
        import yfinance as yf
    except Exception as e:
        LOG.error("yfinance is required for ingestion: %s", e)
        raise

    ticker_obj = yf.Ticker(ticker)
    # yfinance returns a DataFrame with DatetimeIndex
    if start:
        df = ticker_obj.history(start=start, auto_adjust=False)
    else:
        df = ticker_obj.history(period="max", auto_adjust=False)

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    # Standardize column names: Date -> date, Open -> open, etc.
    cols = {c: c.lower() for c in df.columns}
    df.columns = [c.lower() for c in df.columns]
    # Rename adjusted close to adj_close if present
    if "adj close" in df.columns:
        df = df.rename(columns={"adj close": "adj_close"})
    if "date" not in df.columns and df.index.name in ("Date", "date"):
        df = df.reset_index()
    # Ensure required columns exist, map common names
    mapping = {}
    for c in ["open", "high", "low", "close", "adj_close", "volume", "date"]:
        if c not in df.columns:
            # try variants
            if c == "adj_close" and "adjclose" in df.columns:
                mapping["adjclose"] = "adj_close"
            elif c == "date" and "index" in df.columns:
                mapping["index"] = "date"
            else:
                # missing column — allow and fill later
                pass
    if mapping:
        df = df.rename(columns=mapping)

    # Ensure date column exists and is datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    else:
        # try index
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

    # Keep only relevant columns and add ticker column
    # For safety, ensure we have numeric types for OHLCV
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[["date", "open", "high", "low", "close", "adj_close", "volume"]]
    df["ticker"] = ticker
    return df


def _write_outputs(df, ticker: str):
    """Write parquet and csv outputs with canonical schema and metadata.
    Parquet primary, CSV as fallback/backup.
    """
    try:
        import pandas as pd
    except Exception as e:
        LOG.error("pandas required to write outputs: %s", e)
        raise

    # Ensure canonical columns order
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"]]

    # Sort & dedupe
    df = df.drop_duplicates(subset=["date"]).sort_values(by="date").reset_index(drop=True)

    # Write parquet with metadata
    p_parquet = RAW_DIR / f"{ticker}.parquet"
    p_csv = RAW_DIR / f"{ticker}.csv"
    p_parquet.parent.mkdir(parents=True, exist_ok=True)

    # parquet
    try:
        df.to_parquet(p_parquet, index=False)
    except Exception:
        LOG.exception("Failed to write parquet for %s", ticker)
        raise

    # csv fallback
    try:
        df.to_csv(p_csv, index=False)
    except Exception:
        LOG.exception("Failed to write csv for %s", ticker)
        raise

    return p_parquet, p_csv


def fetch_full_history(ticker: str) -> Dict[str, any]:
    """Fetch full history for ticker and save to data/raw/.
    Returns a dict with keys: ticker, rows, start_date, end_date, parquet, csv
    """
    ensure_dirs()
    LOG.info("Fetching full history for %s", ticker)
    df = _df_from_yfinance(ticker)
    if df.empty:
        LOG.warning("No data returned for %s", ticker)
        return {"ticker": ticker, "rows": 0}

    p_parquet, p_csv = _write_outputs(df, ticker)

    # Update registry
    reg = load_registry()
    reg[ticker] = {
        "ticker": ticker,
        "last_update_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_range": [str(df["date"].min().date()), str(df["date"].max().date())],
        "rows": int(len(df)),
        "columns_available": list(df.columns),
    }
    save_registry(reg)

    LOG.info("Wrote %d rows for %s to %s", len(df), ticker, p_parquet)
    return {"ticker": ticker, "rows": len(df), "start_date": str(df["date"].min().date()), "end_date": str(df["date"].max().date()), "parquet": str(p_parquet), "csv": str(p_csv)}


def update_ticker_incremental(ticker: str) -> Dict[str, any]:
    """Update ticker by fetching only new rows since last saved date.
    Appends new rows, dedupes by date, sorts, and writes parquet+csv.
    Returns dict with rows_added etc.
    """
    ensure_dirs()
    LOG.info("Incremental update for %s", ticker)
    p_parquet = RAW_DIR / f"{ticker}.parquet"
    if not p_parquet.exists():
        LOG.info("No existing data for %s, performing full fetch", ticker)
        return fetch_full_history(ticker)

    try:
        import pandas as pd
    except Exception as e:
        LOG.error("pandas is required: %s", e)
        raise

    existing = pd.read_parquet(p_parquet)
    if "date" not in existing.columns:
        LOG.error("Existing file missing 'date' column for %s", ticker)
        raise RuntimeError("Invalid existing parquet schema")

    existing["date"] = pd.to_datetime(existing["date"]).dt.tz_localize(None)
    last_date = existing["date"].max().date()
    start_fetch = last_date + timedelta(days=1)
    # yfinance start param as ISO date
    start_str = start_fetch.isoformat()

    new_df = _df_from_yfinance(ticker, start=start_str)
    if new_df.empty:
        LOG.info("No new rows for %s since %s", ticker, last_date)
        return {"ticker": ticker, "rows_added": 0, "last_date": str(last_date)}

    # concatenate and dedupe
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.tz_localize(None)
    combined = combined.drop_duplicates(subset=["date"]).sort_values(by="date").reset_index(drop=True)

    p_parquet, p_csv = _write_outputs(combined, ticker)

    # Update registry
    reg = load_registry()
    reg[ticker] = {
        "ticker": ticker,
        "last_update_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_range": [str(combined["date"].min().date()), str(combined["date"].max().date())],
        "rows": int(len(combined)),
        "columns_available": list(combined.columns),
    }
    save_registry(reg)

    rows_added = len(combined) - len(existing)
    LOG.info("Appended %d rows for %s (now %d rows).", rows_added, ticker, len(combined))
    return {"ticker": ticker, "rows_added": int(rows_added), "parquet": str(p_parquet), "csv": str(p_csv)}


def validate_raw(ticker: str) -> Dict[str, any]:
    ensure_dirs()
    p_parquet = RAW_DIR / f"{ticker}.parquet"
    if not p_parquet.exists():
        return {"ticker": ticker, "ok": False, "reason": "missing_file"}
    try:
        import pandas as pd
    except Exception as e:
        LOG.error("pandas required: %s", e)
        raise
    df = pd.read_parquet(p_parquet)
    # check required columns
    cols = [c.lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        return {"ticker": ticker, "ok": False, "reason": f"missing_columns: {missing}"}
    # check date sorted and unique
    df["date"] = pd.to_datetime(df["date"])  # no tz concerns here
    if not df["date"].is_monotonic_increasing:
        return {"ticker": ticker, "ok": False, "reason": "date_not_sorted"}
    if df["date"].duplicated().any():
        return {"ticker": ticker, "ok": False, "reason": "duplicate_dates"}
    return {"ticker": ticker, "ok": True, "rows": len(df), "start": str(df["date"].min().date()), "end": str(df["date"].max().date())}
