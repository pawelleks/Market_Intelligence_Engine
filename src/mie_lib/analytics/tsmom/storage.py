"""
Storage module for TSMOM Dashboard.
Handles Persistence of Current Snapshot and Signal History.
"""
import logging
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

LOG = logging.getLogger(__name__)

TSMOM_DATA_DIR = Path("data/tsmom")
CURRENT_SNAPSHOT_PATH = TSMOM_DATA_DIR / "tsmom_current.parquet"
SIGNAL_HISTORY_PATH = TSMOM_DATA_DIR / "tsmom_signals.parquet"

def ensure_data_dir():
    TSMOM_DATA_DIR.mkdir(parents=True, exist_ok=True)

def save_current_snapshot(df: pd.DataFrame):
    """
    Overwrites the current snapshot parquet file.
    """
    ensure_data_dir()
    
    # Enforce schema / column order
    expected_cols = [
        "asof_date", "ticker", "close", "ret_12m", "tsmom_dir", 
        "theoretical_signal", "is_rebalance_date", "next_rebalance_date",
        "last_signal_date", "last_signal_price", "perf_since_signal",
        "signal_today", "signal_changed", "lookback_days", 
        "data_start", "data_end", "rows_used"
    ]
    
    # Filter/Order columns if present
    cols_to_write = [c for c in expected_cols if c in df.columns]
    out_df = df[cols_to_write].copy()
    
    # Ensure types
    if not out_df.empty:
        out_df["asof_date"] = pd.to_datetime(out_df["asof_date"]).dt.date
        out_df["data_start"] = pd.to_datetime(out_df["data_start"]).dt.date
        out_df["data_end"] = pd.to_datetime(out_df["data_end"]).dt.date

    out_df.to_parquet(CURRENT_SNAPSHOT_PATH, index=False)
    LOG.info(f"Saved TSMOM snapshot to {CURRENT_SNAPSHOT_PATH} ({len(out_df)} rows)")

def append_signal_history(new_signals_df: pd.DataFrame, dedup: bool = True):
    """
    Appends new signals to the history file with deduplication.
    Dedup Key: (ticker, event_date, signal, lookback_days)
    """
    ensure_data_dir()
    
    if new_signals_df.empty:
        return

    # Load existing
    if SIGNAL_HISTORY_PATH.exists():
        try:
            existing_df = pd.read_parquet(SIGNAL_HISTORY_PATH)
            # Ensure dates are dates
            existing_df["event_date"] = pd.to_datetime(existing_df["event_date"]).dt.date
        except Exception as e:
            LOG.error(f"Failed to load existing signal history: {e}")
            existing_df = pd.DataFrame()
    else:
        existing_df = pd.DataFrame()

    # Combine
    combined = pd.concat([existing_df, new_signals_df], ignore_index=True)
    
    if dedup:
        # Dedup based on key business fields
        # Keep LAST to allow updates/corrections if re-run with same IDs? 
        # Actually usually keep FIRST to preserve original 'created_at'.
        # But if we re-run logic, maybe we want to overwrite?
        # Specification says: Dedup rule: unique key (ticker, event_date, signal, lookback_days).
        subset = ["ticker", "event_date", "signal", "lookback_days"]
        
        # We want to enable re-runs without duplication.
        # So we drop duplicates.
        before = len(combined)
        combined = combined.drop_duplicates(subset=subset, keep="last")
        after = len(combined)
        if before != after:
            LOG.info(f"Deduped signal history: {before} -> {after} rows")

    # Save
    # Ensure event_date is date
    if "event_date" in combined.columns:
        combined["event_date"] = pd.to_datetime(combined["event_date"]).dt.date
        
    combined.to_parquet(SIGNAL_HISTORY_PATH, index=False)
    LOG.info(f"Appended {len(new_signals_df)} signals to {SIGNAL_HISTORY_PATH}. Total history: {len(combined)}")

def load_current_snapshot() -> pd.DataFrame:
    if CURRENT_SNAPSHOT_PATH.exists():
        return pd.read_parquet(CURRENT_SNAPSHOT_PATH)
    return pd.DataFrame()

def load_signal_history() -> pd.DataFrame:
    """
    Loads signal history as DataFrame.
    """
    if SIGNAL_HISTORY_PATH.exists():
        df = pd.read_parquet(SIGNAL_HISTORY_PATH)
        # Ensure correct date parsing if needed
        if "event_date" in df.columns:
            df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
        return df
    return pd.DataFrame()
