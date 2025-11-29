from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

from mie_lib.utils.paths import DATA_DIR

SNAPSHOT_ROOT = DATA_DIR / "analytics_snapshots" / "markov"
DEFAULT_WINDOWS = ("1Y", "2Y", "5Y", "10Y", "20Y", "50Y", "MAX")
_STATE_LABELS = {"U": "Green", "G": "Green", "N": "Neutral", "D": "Red", "R": "Red"}
_STATE_COLORS = {"Green": "#2e7d32", "Neutral": "#6c757d", "Red": "#c62828"}
STATE_COLUMN_LABELS = {
    "mc_prob_up": "Green",
    "mc_prob_neutral": "Neutral",
    "mc_prob_down": "Red",
}


def list_snapshot_tickers(root: Path | None = None) -> list[str]:
    base = root or SNAPSHOT_ROOT
    if not base.exists():
        return []
    tickers = sorted({p.name.upper() for p in base.iterdir() if p.is_dir()})
    return tickers


def _matrix_dir(ticker: str, mode: str, threshold_bps: int, order: int) -> Path:
    return (
        SNAPSHOT_ROOT
        / ticker.upper()
        / "matrices"
        / str(mode).lower()
        / f"thr{int(threshold_bps)}"
        / f"order{int(order)}"
    )


def matrix_path(ticker: str, mode: str, threshold_bps: int, order: int, window: str) -> Path:
    return _matrix_dir(ticker, mode, threshold_bps, order) / f"{str(window).upper()}.parquet"


def _matrix_metadata_path(ticker: str, mode: str, threshold_bps: int, order: int) -> Path:
    return _matrix_dir(ticker, mode, threshold_bps, order) / "matrix_metadata.json"


def _window_sort_key(window: str) -> int:
    try:
        return DEFAULT_WINDOWS.index(str(window).upper())
    except ValueError:
        return len(DEFAULT_WINDOWS)


@lru_cache(maxsize=256)
def load_matrix_metadata(ticker: str, mode: str, threshold_bps: int, order: int) -> dict:
    path = _matrix_metadata_path(ticker, mode, threshold_bps, order)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k).upper(): v for k, v in payload.items()}


def available_windows_for_combo(ticker: str, mode: str, threshold_bps: int, order: int) -> list[str]:
    meta = load_matrix_metadata(ticker, mode, threshold_bps, order)
    if meta:
        return sorted(meta.keys(), key=_window_sort_key)
    return list(DEFAULT_WINDOWS)


@lru_cache(maxsize=256)
def _state_file_candidates(ticker: str, mode: str, threshold_bps: int) -> tuple[Path, ...]:
    base = SNAPSHOT_ROOT / ticker.upper()
    candidates = (
        base / f"states_thr{int(threshold_bps)}_{str(mode).lower()}.parquet",
        base / f"states_{str(mode).lower()}.parquet",
        base / "states.parquet",
    )
    return candidates


def load_snapshot_states(ticker: str, mode: str, threshold_bps: int) -> pd.DataFrame | None:
    for candidate in _state_file_candidates(ticker, mode, threshold_bps):
        if candidate.exists():
            df = pd.read_parquet(candidate)
            if df is None or df.empty:
                continue
            out = df.copy()
            if "raw_state" not in out.columns:
                if "mc_state_today" in out.columns:
                    out["raw_state"] = out["mc_state_today"].astype(str)
                elif "state" in out.columns:
                    out["raw_state"] = out["state"].astype(str)
            return out
    return None


def load_snapshot_matrix(
    ticker: str,
    mode: str,
    threshold_bps: int,
    order: int,
    window: str,
) -> pd.DataFrame | None:
    path = matrix_path(ticker, mode, threshold_bps, order, window)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def format_state_name(code: str) -> str:
    return _STATE_LABELS.get(str(code).strip().upper(), str(code).upper())


def format_context_label(compact: str) -> str:
    if not compact:
        return ""
    tokens = [format_state_name(ch) for ch in str(compact).strip()]
    return " → ".join(tokens)


def percent_str(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "–"
    try:
        if pd.isna(value):
            return "–"
        return f"{float(value) * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return "–"


def state_color(name_or_code: str) -> str:
    label = name_or_code
    if len(str(name_or_code)) == 1:
        label = format_state_name(name_or_code)
    return _STATE_COLORS.get(label, "#6c757d")


def normalize_snapshot_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().date()


def compute_snapshot_staleness(last_data_date, today: date | None = None) -> dict:
    """Return staleness metadata for a snapshot date."""

    snapshot_date = normalize_snapshot_date(last_data_date)
    today_date = normalize_snapshot_date(today) if today is not None else date.today()
    if today_date is None:
        today_date = date.today()
    if snapshot_date is None:
        return {
            "last_date": None,
            "last_date_iso": None,
            "days_old": None,
            "is_stale": False,
        }
    days_old = (today_date - snapshot_date).days
    return {
        "last_date": snapshot_date,
        "last_date_iso": snapshot_date.isoformat(),
        "days_old": days_old,
        "is_stale": snapshot_date < today_date,
    }


def _raw_state_columns(df: pd.DataFrame) -> Iterable[str]:
    return [c for c in ("row_sum", "counts") if c in df.columns]


def raw_matrix_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ("context", "counts", "row_sum") if c in df.columns]
    return df[cols].copy() if cols else pd.DataFrame()


def reset_metadata_cache_for_tests() -> None:
    load_matrix_metadata.cache_clear()


__all__ = [
    "SNAPSHOT_ROOT",
    "STATE_COLUMN_LABELS",
    "available_windows_for_combo",
    "format_context_label",
    "format_state_name",
    "list_snapshot_tickers",
    "load_matrix_metadata",
    "load_snapshot_matrix",
    "load_snapshot_states",
    "matrix_path",
    "normalize_snapshot_date",
    "percent_str",
    "raw_matrix_columns",
    "reset_metadata_cache_for_tests",
    "state_color",
    "compute_snapshot_staleness",
]
