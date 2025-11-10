#!/usr/bin/env python
"""
Lightweight data integrity check for Market_Intelligence_Engine.

Per-ticker checks (from config/tickers.yml):
- RAW (data/raw/{ticker}.parquet): existence, rows, min/max date, file mtime, real missing trading days (business days minus US Federal holidays)
- FEATURES (data/features/{ticker}.parquet): existence, rows, min/max date, file mtime, real missing trading days (own range), alignment vs RAW (feature-only dates count)

Exit code:
- 0 if no severe issues
- 1 if any missing files or critical problems detected

Notes:
- Offline, read-only. No data writes or network calls.
- Trading day model: business days (Mon–Fri) excluding US Federal holidays as a proxy for market holidays.
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

# Resolve repo root and sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Prefer project config utilities
try:
    from src.data_ingest.yfinance_loader import read_tickers as _read_tickers
except Exception:
    _read_tickers = None  # fallback to YAML parsing below

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

CONFIG_TICKERS = ROOT / "config" / "tickers.yml"
RAW_DIR = ROOT / "data" / "raw"
FEAT_DIR = ROOT / "data" / "features"

# --- Trading day utilities ---

def get_expected_trading_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Return expected trading days between start and end inclusive,
    modeled as business days excluding US Federal holidays.
    """
    if pd.isna(start) or pd.isna(end):
        return pd.DatetimeIndex([])
    start = pd.to_datetime(start).normalize()
    end = pd.to_datetime(end).normalize()
    if end < start:
        return pd.DatetimeIndex([])
    # Business days
    bdays = pd.bdate_range(start=start, end=end)
    if bdays.empty:
        return bdays
    # Remove US Federal holidays (proxy)
    try:
        cal = USFederalHolidayCalendar()
        hol = cal.holidays(start=start, end=end)
        bdays = bdays.difference(pd.DatetimeIndex(hol))
    except Exception:
        # If calendar unavailable, keep bdays as-is
        pass
    return bdays


# --- Ticker loaders ---

def _load_tickers_yaml() -> List[str]:
    if not CONFIG_TICKERS.exists() or yaml is None:
        return []
    try:
        data = yaml.safe_load(CONFIG_TICKERS.read_text()) or {}
    except Exception:
        return []
    tickers: List[str] = []
    # Flexible structures
    if isinstance(data, list):
        tickers.extend(str(t).strip().upper() for t in data if str(t).strip())
    if isinstance(data, dict):
        for key in ("tickers", "universe", "benchmark_tickers", "etfs", "equities"):
            v = data.get(key)
            if isinstance(v, dict):
                tickers.extend(str(t).strip().upper() for t in v.values() if str(t).strip())
            elif isinstance(v, (list, tuple, set)):
                tickers.extend(str(t).strip().upper() for t in v if str(t).strip())
        groups = data.get("groups")
        if isinstance(groups, dict):
            for v in groups.values():
                if isinstance(v, (list, tuple, set)):
                    tickers.extend(str(t).strip().upper() for t in v if str(t).strip())
    # Dedup/sort
    return sorted({t for t in tickers if t})


def resolve_tickers(user_tickers: Optional[str], only_core: bool) -> List[str]:
    # Resolve from CLI or config
    if user_tickers:
        sel = [t.strip().upper() for t in user_tickers.split(",") if t.strip()]
    else:
        if _read_tickers is not None:
            try:
                sel = [t.strip().upper() for t in _read_tickers() if str(t).strip()]
            except Exception:
                sel = _load_tickers_yaml()
        else:
            sel = _load_tickers_yaml()
    if only_core:
        core = {"SPY", "QQQ", "DIA", "IWM"}
        sel = [t for t in sel if t in core]
    return sorted({t for t in sel if t})


# --- File/date helpers ---

def _fmt_dt(dt) -> str:
    if pd.isna(dt):
        return "NA"
    if isinstance(dt, (pd.Timestamp, datetime)):
        return dt.strftime("%Y-%m-%d")
    return str(dt)


def _fmt_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
    except FileNotFoundError:
        return "NA"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _load_dates(path: Path) -> Tuple[pd.DataFrame, pd.DatetimeIndex]:
    if not path.exists():
        return pd.DataFrame(), pd.DatetimeIndex([])
    df = pd.read_parquet(path)
    if "date" not in df.columns:
        # Some files may store date as index; attempt reset
        if df.index.name and df.index.name.lower() == "date":
            df = df.reset_index()
        else:
            # No date column
            return df, pd.DatetimeIndex([])
    dates = pd.to_datetime(df["date"]).dt.tz_localize(None).dropna().sort_values().drop_duplicates()
    return df, pd.DatetimeIndex(dates)


# --- Core checks ---

def _check_raw(ticker: str) -> dict:
    p = RAW_DIR / f"{ticker}.parquet"
    exists = p.exists()
    if not exists:
        return {"exists": False, "rows": 0, "min": None, "max": None, "real_missing": 0, "mtime": "NA"}
    try:
        df, dates = _load_dates(p)
    except Exception as e:
        return {"exists": True, "rows": 0, "min": None, "max": None, "real_missing": -1, "mtime": _fmt_mtime(p), "error": f"read_error: {e}"}
    if dates.empty:
        return {"exists": True, "rows": len(df), "min": None, "max": None, "real_missing": -1, "mtime": _fmt_mtime(p), "error": "missing/invalid date column"}
    exp = get_expected_trading_days(dates.min(), dates.max())
    missing = exp.difference(dates)
    return {
        "exists": True,
        "rows": int(len(df)),
        "min": dates.min(),
        "max": dates.max(),
        "real_missing": int(len(missing)),
        "mtime": _fmt_mtime(p),
        "missing_sample": [d.strftime("%Y-%m-%d") for d in missing[:5]],
    }


def _check_features(ticker: str, raw_dates: pd.DatetimeIndex) -> dict:
    p = FEAT_DIR / f"{ticker}.parquet"
    exists = p.exists()
    if not exists:
        return {"exists": False, "rows": 0, "min": None, "max": None, "real_missing": 0, "mtime": "NA", "misaligned": 0}
    try:
        df, dates = _load_dates(p)
    except Exception as e:
        return {"exists": True, "rows": 0, "min": None, "max": None, "real_missing": -1, "mtime": _fmt_mtime(p), "misaligned": -1, "error": f"read_error: {e}"}
    if dates.empty:
        return {"exists": True, "rows": len(df), "min": None, "max": None, "real_missing": -1, "mtime": _fmt_mtime(p), "misaligned": -1, "error": "missing/invalid date column"}
    # Minimal schema check
    has_ret = "ret_1d" in df.columns
    # Expected trading days in feature range
    exp = get_expected_trading_days(dates.min(), dates.max())
    missing_feat = exp.difference(dates)
    # Alignment vs RAW: features must be subset of RAW dates
    raw_set = set(raw_dates) if len(raw_dates) else set()
    misaligned = 0
    if raw_set:
        misaligned = sum(1 for d in dates if d not in raw_set)
    return {
        "exists": True,
        "rows": int(len(df)),
        "min": dates.min(),
        "max": dates.max(),
        "real_missing": int(len(missing_feat)),
        "mtime": _fmt_mtime(p),
        "misaligned": int(misaligned),
        "has_ret_1d": bool(has_ret),
        "missing_sample": [d.strftime("%Y-%m-%d") for d in missing_feat[:5]],
    }


# --- CLI ---

def _parse_args(argv: Optional[List[str]] = None):
    import argparse
    ap = argparse.ArgumentParser(description="Offline data integrity checks (RAW/FEATURES) with trading-day gaps and alignment")
    ap.add_argument("--tickers", help="Comma list of tickers to check (default: from config)")
    ap.add_argument("--only-core", action="store_true", help="Restrict to core indices (SPY,QQQ,DIA,IWM)")
    return ap.parse_args(argv or sys.argv[1:])


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    tickers = resolve_tickers(args.tickers, args.only_core)
    if not tickers:
        print("[ERROR] No tickers resolved from config/tickers.yml", file=sys.stderr)
        return 1

    print(f"Data integrity check for {len(tickers)} tickers\n")
    had_error = False
    any_missing_samples: List[str] = []

    for t in tickers:
        raw = _check_raw(t)
        # Load raw dates to pass for alignment checks
        raw_dates = pd.DatetimeIndex([])
        if raw.get("exists") and raw.get("min") is not None and raw.get("max") is not None:
            exp = get_expected_trading_days(raw.get("min"), raw.get("max"))
            # But use actual dates from file for alignment
            df_raw, dates_raw = _load_dates(RAW_DIR / f"{t}.parquet")
            raw_dates = dates_raw

        feat = _check_features(t, raw_dates)

        # RAW summary
        if not raw.get("exists"):
            print(f"[RAW]   {t:6s} | MISSING")
            had_error = True
        else:
            rmin = _fmt_dt(raw.get("min"))
            rmax = _fmt_dt(raw.get("max"))
            rm = raw.get("real_missing", 0)
            extra = ""
            if "error" in raw:
                extra = f" | ERROR: {raw['error']}"
                had_error = True
            print(f"[RAW]   {t:6s} | rows={raw['rows']:6d} | data={rmin} → {rmax} | real_missing={rm}{extra}")
            if isinstance(rm, int) and rm > 0:
                sample = raw.get("missing_sample") or []
                if sample:
                    any_missing_samples.append(f"{t}: RAW missing sample {sample}")

        # FEATURES summary
        if not feat.get("exists"):
            print(f"[FEAT]  {t:6s} | MISSING features parquet")
            had_error = True
        else:
            fmin = _fmt_dt(feat.get("min"))
            fmax = _fmt_dt(feat.get("max"))
            fm = feat.get("real_missing", 0)
            mis = feat.get("misaligned", 0)
            flags = []
            if not feat.get("has_ret_1d", False):
                flags.append("NO_ret_1d")
                had_error = True
            if "error" in feat:
                flags.append(f"ERROR:{feat['error']}")
                had_error = True
            flags_str = (" | " + ", ".join(flags)) if flags else ""
            print(f"[FEAT]  {t:6s} | rows={feat['rows']:6d} | data={fmin} → {fmax} | real_missing={fm} | misaligned={mis}{flags_str}")
            if isinstance(fm, int) and fm > 0:
                sample = feat.get("missing_sample") or []
                if sample:
                    any_missing_samples.append(f"{t}: FEAT missing sample {sample}")

        print("-" * 100)

    if had_error or any_missing_samples:
        if any_missing_samples:
            print("[DETAIL] Samples of missing trading days:")
            for line in any_missing_samples:
                print(" -", line)
        print("\n[RESULT] Completed with issues. Review lines marked MISSING / ERROR / NO_ret_1d or nonzero real_missing/misaligned.")
        return 1

    print("\n[RESULT] All checked tickers look consistent (no real missing trading days, features aligned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
