"""Stable paths for Markov analytics artifacts.

Legacy pages import these helpers to locate precomputed matrices and states.
We encode the current directory conventions and avoid performing any I/O here.
"""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data")
ANALYTICS_DIR = DATA_DIR / "analytics" / "markov"
FEATURES_DIR = DATA_DIR / "features"


def markov_matrix_path(ticker: str, mode: str, threshold_bps: int, order: int, window_key: str) -> Path:
    t = str(ticker).upper().strip()
    m = str(mode).lower().strip()
    thr = int(threshold_bps)
    k = int(order)
    win = str(window_key).upper().strip()
    return ANALYTICS_DIR / t / "matrices" / m / f"thr{thr}" / f"order{k}" / f"{win}.parquet"


def states_path(ticker: str, mode: str, threshold_bps: int) -> Path:
    t = str(ticker).upper().strip()
    m = str(mode).lower().strip()
    thr = int(threshold_bps)
    return ANALYTICS_DIR / t / f"states_thr{thr}_{m}.parquet"


__all__ = ["markov_matrix_path", "states_path"]

