from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
import json
import os

import pandas as pd
import numpy as np

from mie_lib.core.state_classification import classify_tri_state as _tri_label

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

# Atomic JSON writer

def _atomic_write_json(obj: dict, path: Path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(obj, ensure_ascii=False))
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


# --- Unified state classification helpers (delegating to core) ---
_EPS = 5e-8  # tolerance retained for binary fallback paths


def _threshold_decimal(threshold_bps: int) -> float:
    return round(float(int(threshold_bps)) / 10000.0, 10)


def classify_tri_state(ret_value: float, threshold_bps: int) -> str:
    """Return raw code 'U'|'N'|'D' using core classify_tri_state as single source of truth."""
    try:
        label = _tri_label(float(ret_value), int(threshold_bps))  # 'Green'|'Neutral'|'Red'
    except Exception:
        label = "Neutral"
    return {"Green": "U", "Neutral": "N", "Red": "D"}.get(label, "N")


def classify_binary_state(ret_value: float, threshold_bps: int) -> str:
    """Binary mode classification: delegate to tri logic then collapse N to nearest side.
    We keep inclusive upper boundary semantics. If Neutral, treat as 'D' by default to
    preserve historical binary behavior unless overridden elsewhere.
    """
    code = classify_tri_state(ret_value, threshold_bps)
    if code == "U":
        return "U"
    return "D"


def classify_tri_state_display(ret_value: float, threshold_bps: int) -> str:
    raw = classify_tri_state(ret_value, threshold_bps)
    return {"U": "Green", "N": "Neutral", "D": "Red"}.get(raw, "Neutral")


def classify_binary_state_display(ret_value: float, threshold_bps: int) -> str:
    raw = classify_binary_state(ret_value, threshold_bps)
    return {"U": "Green", "D": "Red"}.get(raw, "Red")


# Add allowed window mapping & helper
_ALLOWED_WINDOWS = {"1Y":252, "2Y":504, "5Y":1260, "10Y":2520, "20Y":5040, "MAX":None}

def _window_key_from_arg(arg) -> str:
    """Normalize a window argument into canonical key.
    Accepts:
      - str preset (1Y,2Y,5Y,10Y,20Y,MAX)
      - tuple(start_iso,end_iso) custom range -> CUSTOM_YYYYMMDD_YYYYMMDD
    """
    if isinstance(arg, str):
        key = arg.upper().strip()
        if key in _ALLOWED_WINDOWS:
            return key
        return "MAX"  # fallback
    if isinstance(arg, (tuple, list)) and len(arg) == 2:
        try:
            s = str(arg[0]).replace("-","")[:8]
            e = str(arg[1]).replace("-","")[:8]
            return f"CUSTOM_{s}_{e}"
        except Exception:
            return "MAX"
    return "MAX"

# --- State building ---
FEATURES_DIR = DATA_DIR / "features"

def build_states_from_features(ticker: str, thr_bps: int, mode: str) -> str:
    """Build (or overwrite) states parquet for (ticker, threshold, mode).
    Parquet path pattern: data/analytics/markov/{T}/states_thr{thr}_{mode}.parquet
    Returns path as str.
    """
    t = ticker.upper().strip()
    mode = mode.lower().strip()
    path = AN_MKV_DIR / t
    path.mkdir(parents=True, exist_ok=True)
    src = FEATURES_DIR / f"{t}.parquet"
    if not src.exists():
        raise FileNotFoundError(f"features parquet missing for {t}: {src}")
    df = pd.read_parquet(src)
    if "ret_1d" not in df.columns:
        raise ValueError("ret_1d column required for state building")
    # Ensure sorted by date
    df = df.sort_values("date").reset_index(drop=True)
    ret = df["ret_1d"].astype(float)
    if mode == "tri":
        raw_codes = [classify_tri_state(r, thr_bps) for r in ret]
    elif mode == "binary":
        raw_codes = [classify_binary_state(r, thr_bps) for r in ret]
    else:
        raise ValueError(f"Unsupported mode {mode}")
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.tz_localize(None),
        "state": raw_codes,
        "ret_1d": ret.values,
        "thr_bps": int(thr_bps),
        "state_mode": mode,
    })
    dest = path / f"states_thr{int(thr_bps)}_{mode}.parquet"
    _atomic_write_parquet(out, dest)
    return str(dest)


def states_for(ticker: str, thr_bps: int, mode: str) -> pd.DataFrame:
    """Load states parquet for existing (ticker, threshold, mode)."""
    t = ticker.upper().strip()
    p = AN_MKV_DIR / t / f"states_thr{int(thr_bps)}_{mode.lower()}.parquet"
    if not p.exists():
        # attempt build automatically (idempotent)
        build_states_from_features(t, thr_bps, mode)
    return pd.read_parquet(p)


def states_stale(ticker: str, thr_bps: int, mode: str) -> bool:
    """Minimal staleness check used by CLI helpers.

    Returns True if states parquet for (ticker, thr_bps, mode) is missing.
    More elaborate mtime/content comparisons can be added later without breaking CLI.
    """
    t = ticker.upper().strip()
    p = AN_MKV_DIR / t / f"states_thr{int(thr_bps)}_{mode.lower()}.parquet"
    return not p.exists()

# --- Matrix derivation ---

def _slice_window(df_states: pd.DataFrame, window_key: str) -> pd.DataFrame:
    if df_states.empty:
        return df_states
    if window_key.startswith("CUSTOM_"):
        try:
            _, rng = window_key.split("CUSTOM_",1)
            s, e = rng.split("_")
            start = pd.to_datetime(s)
            end = pd.to_datetime(e)
            return df_states[(df_states["date"]>=start)&(df_states["date"]<=end)].copy()
        except Exception:
            return df_states.copy()
    if window_key in _ALLOWED_WINDOWS:
        look = _ALLOWED_WINDOWS[window_key]
        if look is None:
            return df_states.copy()
        return df_states.tail(look).copy()
    return df_states.copy()


def _contexts(series: List[str], order: int) -> List[str]:
    if order <= 0:
        return []
    ctx = []
    for i in range(order, len(series)):
        window = series[i-order:i]
        ctx.append("-".join(window))
    return ctx


def derive_matrix(ticker: str, thr_bps: int, mode: str, order: int, window_key: str) -> pd.DataFrame:
    """Derive (or load cached) transition matrix for given configuration.
    Cached path: data/analytics/markov/{T}/matrices/{mode}/thr{thr}/order{K}/{window_key}.parquet
    Columns tri: mc_prob_up, mc_prob_neutral, mc_prob_down
    Columns binary: mc_prob_up, mc_prob_down
    Includes counts & row_sum.
    """
    t = ticker.upper().strip(); mode = mode.lower().strip(); order = int(order); thr_bps = int(thr_bps)
    mdir = AN_MKV_DIR / t / "matrices" / mode / f"thr{thr_bps}" / f"order{order}"
    mdir.mkdir(parents=True, exist_ok=True)
    dest = mdir / f"{window_key}.parquet"
    if dest.exists():
        try:
            return pd.read_parquet(dest)
        except Exception:
            pass  # recompute on read error
    # Build states (load existing)
    states_df = states_for(t, thr_bps, mode)
    states_df = _slice_window(states_df, window_key)
    if states_df.empty or len(states_df) < order + 2:
        # minimal empty matrix with zeros
        if mode == "tri":
            cols = ["mc_prob_up","mc_prob_neutral","mc_prob_down"]
            base = pd.DataFrame(columns=["context"]+cols+["counts","row_sum"])
        else:
            cols = ["mc_prob_up","mc_prob_down"]
            base = pd.DataFrame(columns=["context"]+cols+["counts","row_sum"])
        _atomic_write_parquet(base, dest)
        # write/update metadata json at order folder (per-window mapping)
        meta_win = {
            "ticker": t,
            "mode": mode,
            "threshold_bps": thr_bps,
            "order": order,
            "window": window_key,
            "rows": int(len(base)),
            "date_min": None,
            "date_max": None,
            "generated": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = mdir/"matrix_metadata.json"
        try:
            existing = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            if not isinstance(existing, dict):
                existing = {}
        except Exception:
            existing = {}
        existing[str(window_key)] = meta_win
        _atomic_write_json(existing, meta_path)
        return base
    seq = list(states_df["state"].astype(str))
    # Determine state universe
    if mode == "tri":
        universe = ["U","N","D"]
        prob_cols = ["mc_prob_up","mc_prob_neutral","mc_prob_down"]
    else:
        universe = ["U","D"]
        prob_cols = ["mc_prob_up","mc_prob_down"]
    contexts = _contexts(seq, order) if order > 0 else []
    next_states = seq[order:]
    # For order=1, contexts align with preceding single state -> treat contexts as that state directly for simpler row index
    if order == 1:
        contexts = seq[:-1]
    # Count transitions
    counts_map: Dict[str, Dict[str,int]] = {}
    for ctx, nxt in zip(contexts, next_states):
        cm = counts_map.setdefault(ctx, {s:0 for s in universe})
        if nxt in cm:
            cm[nxt] += 1
    # Build probability rows with Laplace smoothing (+1)
    rows = []
    for ctx, cm in counts_map.items():
        total = sum(cm.values())
        denom = total + len(universe)
        probs = {s: (cm[s] + 1)/denom for s in universe}
        row = {"context": ctx, "counts": total}
        for s, col in zip(universe, prob_cols):
            row[col] = probs[s]
        row["row_sum"] = sum(probs.values())
        rows.append(row)
    # If some universe states missing as contexts (especially order=1), add zero rows smoothed
    if order == 1:
        present = {r["context"] for r in rows}
        for s in universe:
            if s not in present:
                denom = len(universe)  # total=0
                probs = {u: (1)/denom for u in universe}
                row = {"context": s, "counts": 0}
                for u, col in zip(universe, prob_cols):
                    row[col] = probs[u]
                row["row_sum"] = 1.0
                rows.append(row)
    matrix_df = pd.DataFrame(rows)
    if not matrix_df.empty:
        matrix_df = matrix_df.sort_values("context").reset_index(drop=True)
    _atomic_write_parquet(matrix_df, dest)
    # write/update metadata json at order folder (per-window mapping)
    meta_win = {
        "ticker": t,
        "mode": mode,
        "threshold_bps": thr_bps,
        "order": order,
        "window": window_key,
        "rows": int(len(matrix_df)),
        "date_min": (pd.to_datetime(states_df["date"]).min().isoformat() if not states_df.empty else None),
        "date_max": (pd.to_datetime(states_df["date"]).max().isoformat() if not states_df.empty else None),
        "generated": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = mdir/"matrix_metadata.json"
    try:
        existing = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        if not isinstance(existing, dict):
            existing = {}
    except Exception:
        existing = {}
    existing[str(window_key)] = meta_win
    _atomic_write_json(existing, meta_path)
    return matrix_df

# --- One-step & Multi-step helpers ---

def one_step(matrix_df: pd.DataFrame, mode: str) -> pd.Series:
    """Return average next-day probability distribution across contexts.
    For order=1 matrix where contexts represent states, this equals mean row.
    """
    if matrix_df is None or matrix_df.empty:
        return pd.Series(dtype=float)
    mode = mode.lower().strip()
    if mode == "tri":
        cols = ["mc_prob_up","mc_prob_neutral","mc_prob_down"]
    else:
        cols = ["mc_prob_up","mc_prob_down"]
    return matrix_df[cols].mean()


def multi_step(matrix_df: pd.DataFrame, horizons: List[int], mode: str) -> pd.DataFrame:
    """Compute multi-step probabilities using uniform initial distribution.
    Only valid for order=1 matrices (contexts == states)."""
    if matrix_df is None or matrix_df.empty:
        return pd.DataFrame(columns=horizons)
    mode = mode.lower().strip()
    if mode == "tri":
        cols = ["mc_prob_up","mc_prob_neutral","mc_prob_down"]
        universe = ["U","N","D"]
    else:
        cols = ["mc_prob_up","mc_prob_down"]
        universe = ["U","D"]
    # Build P (states rows -> next distribution) by matching contexts to universe
    P_rows = []
    for u in universe:
        row = matrix_df.loc[matrix_df["context"] == u, cols]
        if row.empty:
            # uniform fallback
            row_vals = np.array([1/len(cols)]*len(cols))
        else:
            row_vals = row.iloc[0][cols].to_numpy()
        P_rows.append(row_vals)
    P = np.vstack(P_rows)  # SxS
    # Uniform initial distribution
    p0 = np.array([1/len(universe)]*len(universe))
    out_rows = []
    for h in horizons:
        if h < 1:
            continue
        Ph = np.linalg.matrix_power(P, h)
        ph = p0 @ Ph
        rec = {"horizon": h}
        for i, col in enumerate(cols):
            rec[col] = ph[i]
        out_rows.append(rec)
    out = pd.DataFrame(out_rows).set_index("horizon")
    return out
