from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
import json
import os

import pandas as pd
import numpy as np

# Atomic parquet writer (idempotent, same-dir temp file)
def _atomic_write_parquet(df: pd.DataFrame, path: Path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp, index=False)
    try:
        os.replace(tmp, path)
        try:
            dfd = os.open(str(path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except Exception:
            pass
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass

# Base dirs (relative to repo root per Bible)
DATA_DIR = Path("data")
AN_MKV_DIR = DATA_DIR / "analytics" / "markov"


def _states_path(ticker: str, thr_bps: int, mode: str) -> Path:
    return AN_MKV_DIR / ticker / f"states_thr{int(thr_bps)}_{mode}.parquet"


def _meta_states_path(ticker: str) -> Path:
    return AN_MKV_DIR / ticker / "meta_states.json"


def _matrix_cache_path(ticker: str, mode: str, thr_bps: int, order: int, window_key: str) -> Path:
    return AN_MKV_DIR / ticker / "matrices" / mode / f"thr{int(thr_bps)}" / f"order{int(order)}" / f"{window_key}.parquet"


def _matrix_meta_path(ticker: str, mode: str, thr_bps: int, order: int) -> Path:
    return AN_MKV_DIR / ticker / "matrices" / mode / f"thr{int(thr_bps)}" / f"order{int(order)}" / "matrix_metadata.json"


def _window_key_from_arg(window: str | Tuple[str, str]) -> str:
    if isinstance(window, str):
        w = window.upper()
        if w in {"1Y", "2Y", "5Y", "10Y", "20Y", "MAX"}:
            return w
        if w.startswith("CUSTOM_"):
            return w
        raise ValueError(f"Unsupported window: {window}")
    else:
        start, end = window
        return f"CUSTOM_{start}_{end}"


def _window_dates_from_states(states: pd.DataFrame, window_key: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    states = states.copy()
    states["date"] = pd.to_datetime(states["date"]).dt.normalize()
    end_all = states["date"].max()
    start_all = states["date"].min()
    if window_key == "MAX":
        return start_all, end_all
    if window_key in {"1Y", "2Y", "5Y", "10Y", "20Y"}:
        years = int(window_key.rstrip("Y"))
        start = max(start_all, end_all - pd.Timedelta(days=365 * years))
        return start, end_all
    if window_key.startswith("CUSTOM_"):
        _, s, e = window_key.split("_", 2)
        return pd.to_datetime(s), pd.to_datetime(e)
    raise ValueError(f"Unsupported window key: {window_key}")


def _context_series(states: pd.Series, order: int) -> pd.Series:
    s = states.astype(str)
    if order < 1:
        raise ValueError("order must be >=1")
    if order == 1:
        return s.copy()
    parts = [s.shift(i) for i in range(order - 1, -1, -1)]
    ctx = pd.concat(parts, axis=1).astype(str).apply(lambda row: "".join(row.values.tolist()), axis=1)
    ctx.iloc[: order - 1] = pd.NA
    return ctx


def states_for(ticker: str, thr_bps: int, mode: str) -> pd.DataFrame:
    p = _states_path(ticker, thr_bps, mode)
    if not p.exists():
        raise FileNotFoundError(f"Markov states not found: {p}")
    df = pd.read_parquet(p)
    # Normalize expected columns
    req = {"date", "state", "ret_1d", "thr_bps", "state_mode"}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"States file missing columns: {missing}")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def _write_meta_states(ticker: str, thr_bps: int, mode: str, states: pd.DataFrame):
    meta_path = _meta_states_path(ticker)
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            meta = {}
    key = f"thr{int(thr_bps)}_{mode}"
    meta[key] = {
        "rows": int(len(states)),
        "first_date": str(pd.to_datetime(states["date"]).min().date()),
        "last_date": str(pd.to_datetime(states["date"]).max().date()),
        "hash_hint": f"{ticker}:{thr_bps}:{mode}:{len(states)}",
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))


def build_states_from_features(ticker: str, thr_bps: int, mode: str) -> str:
    """Compute full-history states from features and write the cache parquet + meta.
    Returns path to states parquet.
    Binary mode logic is symmetric: Up if ret_1d >= +th, Down if ret_1d <= -th, else sign fallback (Up if >=0 else Down).
    Tri mode keeps neutral band: Up if > +th, Down if < -th else Neutral.
    """
    from src.analytics.markov.markov_engine import _load_features
    df = _load_features(ticker)
    th = float(thr_bps) / 10000.0
    if mode == "tri":
        st = pd.Series(np.where(df["ret_1d"] > th, "U", np.where(df["ret_1d"] < -th, "D", "N")), index=df.index)
    else:
        # Binary mode per spec: Up if ret_1d >= +threshold, Down otherwise (threshold-dependent classification)
        ret = df["ret_1d"].astype(float).to_numpy()
        st_arr = np.where(ret >= th, "U", "D")
        st = pd.Series(st_arr, index=df.index)
    out = pd.DataFrame({
        "date": df["date"],
        "state": st.astype(str),
        "ret_1d": df["ret_1d"].astype(float),
        "thr_bps": int(thr_bps),
        "state_mode": mode,
    })
    p = _states_path(ticker, thr_bps, mode)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_parquet(out, p)
    _write_meta_states(ticker, thr_bps, mode, out)
    return str(p)


def states_stale(ticker: str, thr_bps: int, mode: str) -> bool:
    """Return True if states cache is missing or stale vs features based on last_date/rows."""
    p = _states_path(ticker, thr_bps, mode)
    meta_p = _meta_states_path(ticker)
    if not p.exists() or not meta_p.exists():
        return True
    from src.analytics.markov.markov_engine import _load_features
    try:
        meta = json.loads(meta_p.read_text())
    except Exception:
        return True
    key = f"thr{int(thr_bps)}_{mode}"
    info = meta.get(key) or {}
    try:
        df = _load_features(ticker)
        feat_last = pd.to_datetime(df["date"]).max().date()
        cache_last = pd.to_datetime(info.get("last_date")).date() if info.get("last_date") else None
        if cache_last is None or feat_last != cache_last:
            return True
        # optional rows check
        if int(info.get("rows", 0)) != len(df):
            return True
    except Exception:
        return True
    return False


def derive_matrix(ticker: str, thr_bps: int, mode: str, order: int, window: str | Tuple[str, str]) -> pd.DataFrame:
    """Derive K-order Markov matrix from cached states within a window; cache and return DataFrame.
    Always recomputes (overwrites) cache to avoid stale threshold collisions.
    Includes: context, mc_prob_up, mc_prob_neutral (tri), mc_prob_down, row_sum, counts.
    """
    window_key = _window_key_from_arg(window)
    cache_p = _matrix_cache_path(ticker, mode, thr_bps, order, window_key)

    # Load thresholded states; if missing, raise clear ValueError with CLI hint
    try:
        st_df = states_for(ticker, thr_bps, mode)
    except FileNotFoundError as e:
        hint = (
            f"States missing for (ticker={ticker}, mode={mode}, thr={thr_bps}).\n"
            f"Run: python cli/mie.py build-markov --ticker {ticker} --order {int(order)} --state-mode {mode} --threshold-bps {int(thr_bps)} --window {window_key}"
        )
        raise ValueError(hint) from e

    start, end = _window_dates_from_states(st_df, window_key)
    mask = (st_df["date"] >= start) & (st_df["date"] <= end)
    sl = st_df.loc[mask].reset_index(drop=True)
    if sl.empty:
        raise ValueError("No states within selected window")

    ctx = _context_series(sl["state"], order)
    next_state = sl["state"].shift(-1)

    # counts per (context,next)
    ct = pd.crosstab(ctx.dropna(), next_state[ctx.notna()])
    states = ["U", "N", "D"] if mode == "tri" else ["U", "D"]
    for s in states:
        if s not in ct.columns:
            ct[s] = 0
    ct = ct.reindex(columns=states, fill_value=0)
    ct.index.name = "context"
    ct = ct.reset_index()

    ct["counts"] = ct[states].sum(axis=1)
    sm = ct.copy()
    for s in states:
        sm[s] = sm[s].astype(float) + 1.0
    denom = sm[states].sum(axis=1)
    probs = sm[states].div(denom, axis=0)

    out = pd.DataFrame({"context": ct["context"].astype(str)})
    out["mc_prob_up"] = probs["U"].astype(float)
    if mode == "tri":
        out["mc_prob_neutral"] = probs.get("N", pd.Series(0.0, index=out.index)).astype(float)
    out["mc_prob_down"] = probs["D"].astype(float)
    prob_cols = ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if mode == "tri" else ["mc_prob_up", "mc_prob_down"]
    out["row_sum"] = out[prob_cols].sum(axis=1)
    out["counts"] = ct["counts"].astype(int)

    cache_p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_parquet(out, cache_p)

    # Write/append matrix metadata JSON alongside
    meta_p = _matrix_meta_path(ticker, mode, thr_bps, order)
    meta = {}
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text())
        except Exception:
            meta = {}
    meta[window_key] = {
        "ticker": ticker,
        "mode": mode,
        "threshold_bps": int(thr_bps),
        "order": int(order),
        "window": window_key,
        "date_range": {"start": str(start.date()), "end": str(end.date())},
        "build_version": "states-first-v1",
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "matrix_path": str(cache_p),
    }
    meta_p.write_text(json.dumps(meta, indent=2))
    return out


def one_step(row: pd.Series, mode: str) -> Tuple[str, float]:
    cols = ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if mode == "tri" else ["mc_prob_up", "mc_prob_down"]
    vals = row[cols].astype(float).values
    idx = int(np.argmax(vals)) if len(vals) else 0
    name = ["Green", "Neutral", "Red"][: len(cols)][idx]
    p = float(vals[idx]) if len(vals) else float("nan")
    return name, p


def multi_step(P: pd.DataFrame, horizons: List[int], mode: str) -> pd.DataFrame:
    cols = ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if mode == "tri" else ["mc_prob_up", "mc_prob_down"]
    if any(c not in P.columns for c in cols):
        raise ValueError("Invalid matrix DataFrame for multi-step")
    trans = P[cols].to_numpy(dtype=float)
    # Approximate a generic transition by averaging across contexts
    trow = np.nanmean(trans, axis=0)
    n = len(cols)
    T = np.tile(trow, (n, 1))
    # start from trow as initial distribution
    pi = trow / (trow.sum() if trow.sum() else 1.0)
    out = {}
    for h in horizons:
        Ph = T.copy()
        for _ in range(max(1, h - 1)):
            Ph = Ph @ T
        vec = pi @ Ph
        out[h] = {cols[i]: vec[i] for i in range(n)}
    return pd.DataFrame(out).T
