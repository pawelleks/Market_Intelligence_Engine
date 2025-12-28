"""
Hybrid Storage for Skew/PCR Data.

Implements three storage patterns for optimal read performance:
1. by_ticker/{TICKER}.parquet - for historical charts (single ticker, all dates)
2. by_date/date={DATE}/data.parquet - for heatmaps (all tickers, single date)
3. latest.json - for API fast-path (no Parquet overhead)
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd

LOG = logging.getLogger(__name__)

# Storage directories
SKEW_DIR = Path("data/analytics/skew")
BY_TICKER_DIR = SKEW_DIR / "by_ticker"
BY_DATE_DIR = SKEW_DIR / "by_date"
LATEST_PATH = SKEW_DIR / "latest.json"


def save_skew_metrics(ticker: str, date_str: str, metrics: Dict[str, Any]) -> None:
    """
    Write metrics to all three storage locations.
    
    This writes to:
    1. by_ticker/{ticker}.parquet - append/upsert by date
    2. by_date/date={date}/data.parquet - append/upsert by ticker
    3. latest.json - update cache
    
    Args:
        ticker: Underlying ticker symbol
        date_str: YYYY-MM-DD
        metrics: Dict with skew_25d, pcr_volume, pcr_oi, sentiment_score, regime, etc.
    """
    # Ensure directories exist
    BY_TICKER_DIR.mkdir(parents=True, exist_ok=True)
    date_partition = BY_DATE_DIR / f"date={date_str}"
    date_partition.mkdir(parents=True, exist_ok=True)
    
    # Create row DataFrame
    row = pd.DataFrame([{
        "ticker": ticker,
        "date": pd.to_datetime(date_str).date(),
        "skew_25d": metrics.get("skew_25d"),
        "pcr_volume": metrics.get("pcr_volume"),
        "pcr_oi": metrics.get("pcr_oi"),
        "sentiment_score": metrics.get("sentiment_score"),
        "regime": metrics.get("regime"),
        "spot": metrics.get("spot"),
        "source": metrics.get("source", "unknown"),
        "options_count": metrics.get("options_count", 0),
        "computed_at": pd.Timestamp.now(tz="UTC")
    }])
    
    # ========== 1. By-Ticker Storage (for historical charts) ==========
    _save_by_ticker(ticker, row)
    
    # ========== 2. By-Date Partition (for heatmaps) ==========
    _save_by_date(date_str, row)
    
    # ========== 3. Update Latest Cache (for API fast-path) ==========
    _update_latest_cache(ticker, date_str, metrics)


def _save_by_ticker(ticker: str, row: pd.DataFrame) -> None:
    """Append/upsert row to ticker-specific parquet file."""
    ticker_path = BY_TICKER_DIR / f"{ticker}.parquet"
    
    try:
        if ticker_path.exists():
            existing = pd.read_parquet(ticker_path)
            # Convert date columns for proper comparison
            existing["date"] = pd.to_datetime(existing["date"]).dt.date
            row["date"] = pd.to_datetime(row["date"]).dt.date
            # Combine and deduplicate
            combined = pd.concat([existing, row], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
        else:
            combined = row
        
        combined.to_parquet(ticker_path, index=False)
        
    except Exception as e:
        LOG.error(f"Failed to save by_ticker for {ticker}: {e}")
        raise


def _save_by_date(date_str: str, row: pd.DataFrame) -> None:
    """Append/upsert row to date-partitioned parquet file."""
    date_partition = BY_DATE_DIR / f"date={date_str}"
    date_path = date_partition / "data.parquet"
    
    try:
        if date_path.exists():
            existing = pd.read_parquet(date_path)
            # Combine and deduplicate by ticker
            combined = pd.concat([existing, row], ignore_index=True)
            combined = combined.drop_duplicates(subset=["ticker"], keep="last")
        else:
            combined = row
        
        combined.to_parquet(date_path, index=False)
        
    except Exception as e:
        LOG.error(f"Failed to save by_date for {date_str}: {e}")
        raise


def _update_latest_cache(ticker: str, date_str: str, metrics: Dict[str, Any]) -> None:
    """
    Update the JSON cache atomically.
    Uses temp file + rename for atomic write.
    """
    SKEW_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        # Load existing
        if LATEST_PATH.exists():
            with open(LATEST_PATH, "r") as f:
                latest = json.load(f)
        else:
            latest = {"as_of": None, "tickers": {}}
        
        # Update
        latest["as_of"] = date_str
        latest["updated_at"] = datetime.now().isoformat()
        latest["tickers"][ticker] = {
            "skew_25d": metrics.get("skew_25d"),
            "pcr_volume": metrics.get("pcr_volume"),
            "pcr_oi": metrics.get("pcr_oi"),
            "sentiment_score": metrics.get("sentiment_score"),
            "regime": metrics.get("regime"),
            "spot": metrics.get("spot")
        }
        
        # Atomic write (write to temp, then rename)
        tmp_path = LATEST_PATH.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(latest, f, indent=2)
        tmp_path.rename(LATEST_PATH)
        
    except Exception as e:
        LOG.error(f"Failed to update latest cache: {e}")
        # Don't raise - cache update failure shouldn't fail the pipeline


# ========== Read Functions for API ==========

def load_ticker_history(ticker: str, days: int = 90) -> Optional[pd.DataFrame]:
    """
    Load historical data for a single ticker.
    Used for charting a ticker's skew history.
    
    Args:
        ticker: Underlying ticker symbol
        days: Number of days of history to return
        
    Returns:
        DataFrame with historical metrics, or None if not found
    """
    path = BY_TICKER_DIR / f"{ticker}.parquet"
    
    if not path.exists():
        return None
    
    try:
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"])
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        return df[df["date"] >= cutoff].sort_values("date")
    except Exception as e:
        LOG.error(f"Failed to load ticker history for {ticker}: {e}")
        return None


def load_date_snapshot(date_str: str) -> Optional[pd.DataFrame]:
    """
    Load all tickers for a specific date.
    Used for heatmaps and daily dashboards.
    
    Args:
        date_str: YYYY-MM-DD
        
    Returns:
        DataFrame with all tickers' metrics for that date, or None if not found
    """
    path = BY_DATE_DIR / f"date={date_str}" / "data.parquet"
    
    if not path.exists():
        return None
    
    try:
        return pd.read_parquet(path)
    except Exception as e:
        LOG.error(f"Failed to load date snapshot for {date_str}: {e}")
        return None


def load_latest() -> Dict[str, Any]:
    """
    Load the cached latest values.
    Used for API fast-path - no Parquet parsing overhead.
    
    Returns:
        Dict with 'as_of', 'updated_at', and 'tickers' containing latest metrics
    """
    try:
        if LATEST_PATH.exists():
            with open(LATEST_PATH) as f:
                return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        LOG.error(f"Failed to load latest cache: {e}")
    
    return {"as_of": None, "tickers": {}}


def list_available_dates(limit: int = 30) -> List[str]:
    """
    List available dates in the by_date storage.
    
    Args:
        limit: Maximum number of dates to return
        
    Returns:
        List of date strings (YYYY-MM-DD), most recent first
    """
    if not BY_DATE_DIR.exists():
        return []
    
    dates = []
    for path in BY_DATE_DIR.iterdir():
        if path.is_dir() and path.name.startswith("date="):
            date_str = path.name.replace("date=", "")
            dates.append(date_str)
    
    # Sort descending (most recent first)
    dates.sort(reverse=True)
    return dates[:limit]


def list_available_tickers() -> List[str]:
    """
    List tickers with available historical data.
    
    Returns:
        List of ticker symbols
    """
    if not BY_TICKER_DIR.exists():
        return []
    
    tickers = []
    for path in BY_TICKER_DIR.iterdir():
        if path.suffix == ".parquet":
            tickers.append(path.stem)
    
    return sorted(tickers)
