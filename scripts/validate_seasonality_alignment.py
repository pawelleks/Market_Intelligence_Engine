#!/usr/bin/env python
"""Validate alignment between seasonality base returns and features returns.

Compares daily simple returns in:
  data/seasonality/base/{ticker}.parquet  (column: r)
with
  data/features/{ticker}.parquet          (column: ret_1d)

Tolerance: |r - ret_1d| < 1 bp (1e-4).
Warn (do not fail) for short-history tickers (years < MIN_VALID_YEARS).
Exit code:
  0 -> all core tickers within tolerance (SPY/QQQ/DIA/IWM) or skipped due to missing data
  1 -> any core ticker has mismatches above tolerance

Follows logging & reporting tone from ARCHITECT_BIBLE.
"""
from __future__ import annotations
import sys
from pathlib import Path
from dataclasses import dataclass
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SEAS_BASE_DIR = ROOT / "data" / "seasonality" / "base"
FEAT_DIR = ROOT / "data" / "features"
SEAS_CFG = ROOT / "config" / "seasonality.yml"
TICKERS_CFG = ROOT / "config" / "tickers.yml"
CORE_TICKERS = ["SPY", "QQQ", "DIA", "IWM"]
TOL = 1e-4  # 1 bp in decimal return units

@dataclass
class TickerResult:
    ticker: str
    rows_seas: int = 0
    rows_feat: int = 0
    max_abs_diff: float | None = None
    mismatches: int = 0
    compared_rows: int = 0
    missing_files: bool = False
    short_history: bool = False
    years: int | None = None
    note: str = ""

def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}

def load_tickers_from_config() -> list[str]:
    cfg = load_yaml(TICKERS_CFG)
    tickers: set[str] = set()
    for k in ("tickers", "universe", "etfs", "equities"):
        v = cfg.get(k)
        if isinstance(v, list):
            tickers.update(str(x).strip().upper() for x in v if str(x).strip())
        elif isinstance(v, dict):
            tickers.update(str(x).strip().upper() for x in v.values() if str(x).strip())
    groups = cfg.get("groups")
    if isinstance(groups, dict):
        for v in groups.values():
            if isinstance(v, list):
                tickers.update(str(x).strip().upper() for x in v if str(x).strip())
    return sorted(tickers) or CORE_TICKERS

def load_seasonality_base(ticker: str) -> pd.DataFrame | None:
    p = SEAS_BASE_DIR / f"{ticker}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        return df
    except Exception:
        return None

def load_features(ticker: str) -> pd.DataFrame | None:
    p = FEAT_DIR / f"{ticker}.parquet"
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception:
        return None

def evaluate_ticker(ticker: str, min_valid_years: int) -> TickerResult:
    res = TickerResult(ticker=ticker)
    seas = load_seasonality_base(ticker)
    feat = load_features(ticker)
    if seas is None or feat is None:
        res.missing_files = True
        res.note = "missing seasonality or features parquet"
        return res

    # Basic schema assertions (non-fatal reporting)
    res.rows_seas = len(seas)
    res.rows_feat = len(feat)

    # Parse dates
    if "date" not in seas.columns or "date" not in feat.columns:
        res.note = "missing date column(s)"
        return res
    seas_dates = pd.to_datetime(seas["date"], utc=True)
    feat_dates = pd.to_datetime(feat["date"], utc=True)

    # Years count
    try:
        res.years = int(seas_dates.dt.year.nunique())
        if res.years < min_valid_years:
            res.short_history = True
    except Exception:
        pass

    # Required return columns
    if "r" not in seas.columns or "ret_1d" not in feat.columns:
        res.note = "missing return columns (r or ret_1d)"
        return res

    # Align on overlapping dates only
    seas_sub = seas.set_index(seas_dates)["r"].astype(float)
    feat_sub = feat.set_index(feat_dates)["ret_1d"].astype(float)
    common_idx = seas_sub.index.intersection(feat_sub.index)
    if common_idx.empty:
        res.note = "no overlapping dates"
        return res

    seas_aligned = seas_sub.loc[common_idx]
    feat_aligned = feat_sub.loc[common_idx]

    diffs = (seas_aligned - feat_aligned).abs()
    res.max_abs_diff = float(diffs.max()) if len(diffs) else None
    res.mismatches = int((diffs > TOL).sum())
    res.compared_rows = len(diffs)
    return res

def main(argv: list[str]) -> int:
    cfg = load_yaml(SEAS_CFG)
    min_years = int(cfg.get("MIN_VALID_YEARS", 5))
    tickers = load_tickers_from_config()

    print(f"Seasonality alignment validation (tolerance: {TOL:.5f})\n")
    header = f"{'Ticker':6s} | {'Rows(seas)':10s} | {'Rows(feat)':10s} | {'Compared':8s} | {'MaxDiff':10s} | {'Mismatch>1bp':13s} | {'Years':5s} | Notes"
    print(header)
    print("-" * len(header))

    failures = 0
    for t in tickers:
        res = evaluate_ticker(t, min_years)
        maxdiff_str = f"{res.max_abs_diff:.6f}" if res.max_abs_diff is not None else "NA"
        note_parts = []
        if res.missing_files:
            note_parts.append("missing files")
        if res.short_history:
            note_parts.append("short history")
        if res.note:
            note_parts.append(res.note)
        note = ", ".join(note_parts) if note_parts else "ok"
        print(f"{t:6s} | {res.rows_seas:10d} | {res.rows_feat:10d} | {res.compared_rows:8d} | {maxdiff_str:10s} | {res.mismatches:13d} | {res.years if res.years is not None else 0:5d} | {note}" )
        if t in CORE_TICKERS and res.mismatches > 0:
            failures += 1

    if failures:
        print(f"\n[RESULT] Alignment check FAILED for {failures} core tickers (mismatches > tolerance).")
        return 1
    print("\n[RESULT] Alignment check passed (core tickers within tolerance or skipped).")
    return 0

if __name__ == "main":  # defensive; typical entrypoint below
    pass

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
