"""Canonical path helpers for data and analytics artifacts.

This module centralizes filesystem paths used by pages and library code.
Only path definitions and helpers live here; no I/O or computation.
"""
from __future__ import annotations

from pathlib import Path

# Root and top-level data dirs
ROOT: Path = Path(".")  # keep relative to project working dir
DATA_DIR: Path = Path("data")
RAW_DIR: Path = DATA_DIR / "raw"
FEATURES_DIR: Path = DATA_DIR / "features"
META_DIR: Path = DATA_DIR / "meta"

# Analytics roots
MARKOV_DIR: Path = DATA_DIR / "analytics" / "markov"
HMM_DIR: Path = DATA_DIR / "analytics" / "hmm"
OPTIONS_DIR: Path = DATA_DIR / "analytics" / "options"
SEASONALITY_DIR: Path = DATA_DIR / "seasonality"

# ---------- Feature layer helpers ----------

def features_parquet_path(ticker: str) -> Path:
    return FEATURES_DIR / f"{ticker}.parquet"


# ---------- Markov helpers (engine flat outputs) ----------

def markov_out_dir(ticker: str) -> Path:
    return MARKOV_DIR / f"{ticker}"


def markov_states_path(ticker: str) -> Path:
    return markov_out_dir(ticker) / "states.parquet"


def markov_counts_path(ticker: str, order: int) -> Path:
    return markov_out_dir(ticker) / f"counts_order{int(order)}.parquet"


def markov_matrix_path_flat(ticker: str, order: int) -> Path:
    return markov_out_dir(ticker) / f"matrix_order{int(order)}.parquet"


def markov_predictions_path(ticker: str) -> Path:
    return markov_out_dir(ticker) / "predictions.parquet"


def markov_metadata_path(ticker: str) -> Path:
    return markov_out_dir(ticker) / "metadata.json"


# ---------- Markov matrix grid (UI consumption) ----------

def markov_matrix_grid_path(ticker: str, state_mode: str, threshold_bps: int, order: int, window_key: str) -> Path:
    sm = str(state_mode).strip().lower()
    thr = int(threshold_bps)
    ord_i = int(order)
    win = str(window_key).strip().upper()
    return MARKOV_DIR / ticker / "matrices" / sm / f"thr{thr}" / f"order{ord_i}" / f"{win}.parquet"


def markov_matrix_grid_meta_dir(ticker: str, state_mode: str, threshold_bps: int, order: int) -> Path:
    sm = str(state_mode).strip().lower()
    thr = int(threshold_bps)
    ord_i = int(order)
    return MARKOV_DIR / ticker / "matrices" / sm / f"thr{thr}" / f"order{ord_i}"


# ---------- HMM helpers ----------

def hmm_out_dir(ticker: str) -> Path:
    return HMM_DIR / f"{ticker}"


def hmm_std_out_dir(ticker: str, window_years: int | str, n_states: int) -> Path:
    w_str = str(window_years).lower()
    if w_str == "max":
        win_part = "winMax"
    else:
        win_part = f"win{int(window_years)}y"
    return HMM_DIR / f"{ticker}" / win_part / f"states{int(n_states)}"


# ---------- Seasonality helpers ----------

def seasonality_base_path(ticker: str) -> Path:
    return SEASONALITY_DIR / "base" / f"{ticker}.parquet"


# ---------- Expected moves helpers ----------

def options_expected_moves_path(ticker: str) -> Path:
    slug = str(ticker).strip().lower()
    return OPTIONS_DIR / f"{slug}_expected_moves.parquet"


def options_weekly_reference_path(ticker: str) -> Path:
    slug = str(ticker).strip().lower()
    return OPTIONS_DIR / f"{slug}_weekly_reference.parquet"


def options_manifest_path() -> Path:
    return META_DIR / "expected_moves_manifest.json"


__all__ = [
    "ROOT",
    "DATA_DIR",
    "RAW_DIR",
    "FEATURES_DIR",
    "META_DIR",
    "MARKOV_DIR",
    "HMM_DIR",
    "OPTIONS_DIR",
    "SEASONALITY_DIR",
    # Features
    "features_parquet_path",
    # Markov
    "markov_out_dir",
    "markov_states_path",
    "markov_counts_path",
    "markov_matrix_path_flat",
    "markov_predictions_path",
    "markov_metadata_path",
    "markov_matrix_grid_path",
    "markov_matrix_grid_meta_dir",
    # HMM
    "hmm_out_dir",
    "hmm_std_out_dir",
    # Seasonality
    "seasonality_base_path",
    # Expected moves
    "options_expected_moves_path",
    "options_weekly_reference_path",
    "options_manifest_path",
]
