# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)
# Constants for repo paths
from pathlib import Path
DATA = ROOT / "data"
# Type assertions to avoid shadowing issues
assert isinstance(ROOT, Path)
assert isinstance(DATA, Path)
assert DATA.is_absolute()
# Do not reassign ROOT or DATA anywhere below

import streamlit as st
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import yaml
import datetime as _dt
import numpy as _np
from matplotlib.patches import Rectangle as _Rect

from app.ui.theme import css_inject, get_tokens, mpl_style
from app.ui.components import SectionHeader, DataStatus, plot_mpl
from app.ui.components import read_parquet_safe, read_csv_safe, read_json_safe, fmt_percent_one_decimal
# Lightweight stdlib for fs checks
import os
import hashlib as _hashlib

# Temporary debug flag for binary threshold panel
DEBUG_BINARY_THRESHOLD = True


def _get_ticker_from_state(default: str = "SPY") -> str:
    """Return a clean string ticker from session state with robust fallbacks.

    - Prefer 'mk_ticker', else 'ticker'
    - If value is list/tuple/Series -> take first element
    - If dict -> use .get('value') or first key
    - If None/empty/invalid -> return default
    - Always return uppercase, stripped string
    """
    cand = None
    try:
        has_ss = hasattr(st, "session_state")
        cand = st.session_state.get("mk_ticker") if has_ss else None
        # Explicit emptiness checks to avoid pandas truth ambiguity
        needs_fallback = (
            cand is None or
            (isinstance(cand, str) and not cand.strip()) or
            (isinstance(cand, (list, tuple)) and len(cand) == 0)
        )
        if not needs_fallback and 'pandas' in sys.modules:
            import pandas as _pd
            if isinstance(cand, _pd.Series) and cand.empty:
                needs_fallback = True
        if needs_fallback:
            cand = st.session_state.get("ticker") if has_ss else None
    except Exception:
        cand = None
    # Normalize containers
    if isinstance(cand, (list, tuple)):
        cand = cand[0] if cand else None
    else:
        try:
            import pandas as _pd
            if isinstance(cand, _pd.Series):
                cand = cand.iloc[0] if not cand.empty else None
            elif isinstance(cand, dict):
                cand = cand.get("value") or (next(iter(cand.keys())) if cand else None)
        except Exception:
            pass
    # Final sanitize
    if isinstance(cand, str) and cand.strip():
        return cand.strip().upper()
    return (default or "SPY").strip().upper()


def _as_context_key(obj) -> str:
    """Convert various context-like inputs to canonical 'G-N-R' string.

    - str -> return as-is
    - list/tuple/np.ndarray/pandas.Series -> join tokens with '-'
    - else -> ''
    """
    if isinstance(obj, str):
        return obj
    try:
        import numpy as _n
        import pandas as _pd
        if isinstance(obj, (list, tuple, _n.ndarray, _pd.Series)):
            parts = [str(x) for x in list(obj) if str(x)]
            return "-".join(parts)
    except Exception:
        pass
    return ""


def _normalize_window_value(x) -> str:
    """Normalize various window inputs into one of {1Y,2Y,5Y,10Y,20Y,MAX,CUSTOM}. Fallback to 1Y."""
    allowed = {"1Y","2Y","5Y","10Y","20Y","MAX","CUSTOM"}
    if isinstance(x, (int, float)):
        if int(x) == 1:
            return "1Y"
        if int(x) == 2:
            return "2Y"
    s = str(x or "").upper().strip()
    if s in allowed:
        return s
    if s in {"1"}: return "1Y"
    if s in {"2"}: return "2Y"
    if s == "CUSTOM" or s == "CUSTOM".upper():
        return "CUSTOM"
    if s == "MAX":
        return "MAX"
    return "1Y"


def _safe_width(width):
    """Return a Streamlit-safe width value. Prefer 'stretch'; clamp numeric to >=300."""
    if width in (None, 0):
        return "stretch"
    if isinstance(width, int):
        return max(width, 300)
    if isinstance(width, str):
        return width
    return "stretch"


def _normalize_mode(mode_in) -> str:
    """Map various inputs to canonical 'binary' or 'tri'. Raise ValueError if unsupported."""
    m = str(mode_in).strip().lower() if not isinstance(mode_in, int) else mode_in
    if m in (0, "0", "bin", "binary"):
        return "binary"
    if m in (1, "1", "tri", "tri-state", "tri_state", "ternary"):
        return "tri"
    if isinstance(mode_in, str) and mode_in.strip().lower() in {"binary", "tri"}:
        return mode_in.strip().lower()
    raise ValueError(f"Unsupported mode: {mode_in}")


def _matrix_exact_path(ticker: str, mode: str, thr: int, order: int, window: str) -> Path:
    mode = str(mode).lower().strip()
    window = str(window).upper().strip()
    return DATA/"analytics"/"markov"/ticker/"matrices"/mode/f"thr{int(thr)}"/f"order{int(order)}"/f"{window}.parquet"


def _nearest_available_threshold(ticker: str, mode: str, order: int, window: str, requested_thr: int) -> int | None:
    # Look up by scanning threshold directories under matrices/{mode}
    mdir = DATA/"analytics"/"markov"/ticker/"matrices"/str(mode).lower()
    if not mdir.exists():
        return None
    candidates: list[tuple[int,int]] = []  # (absdiff, thr)
    for thr_dir in mdir.glob("thr*/"):
        try:
            tnum = int(thr_dir.name.replace("thr", ""))
        except Exception:
            continue
        p = thr_dir/f"order{int(order)}"/f"{str(window).upper()}.parquet"
        if p.exists():
            candidates.append((abs(int(requested_thr)-tnum), tnum))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]


@st.cache_data(show_spinner=False)
def _load_matrix_cached_by_params(
    ticker: str,
    mode: str,
    thr: int,
    order: int,
    window: str,
    path_str: str,
    mtime: float,
    cache_version: str = "v1",
):
    import pandas as pd
    return pd.read_parquet(path_str)


def _load_matrix_for_selection(
    ticker: str,
    mode: str,
    thr: int,
    order: int,
    window: str,
    allow_fallback: bool = True,
):
    """Resolve and load matrix for (ticker, mode, thr, order, window) with optional nearest-threshold fallback.

    Returns (df, info) where info includes:
      - path (Path)
      - requested: dict
      - resolved: dict
      - fallback_used: bool
    """
    mode_l = str(mode).lower().strip()
    thr_i = int(thr)
    win_u = str(window).upper().strip()
    # Exact path
    p = _matrix_exact_path(ticker, mode_l, thr_i, order, win_u)
    used_thr = thr_i
    fallback_used = False
    if not p.exists() and allow_fallback:
        near = _nearest_available_threshold(ticker, mode_l, order, win_u, thr_i)
        if near is not None and near != thr_i:
            used_thr = near
            p = _matrix_exact_path(ticker, mode_l, used_thr, order, win_u)
            fallback_used = p.exists()
    if not p.exists():
        raise FileNotFoundError(str(p))
    st_stat = p.stat()
    df = _load_matrix_cached_by_params(
        ticker=ticker,
        mode=mode_l,
        thr=used_thr,
        order=int(order),
        window=win_u,
        path_str=str(p),
        mtime=float(st_stat.st_mtime),
        cache_version="v1",
    )
    info = {
        "path": p,
        "requested": {"ticker": ticker, "mode": mode_l, "thr": thr_i, "order": int(order), "window": win_u},
        "resolved": {"ticker": ticker, "mode": mode_l, "thr": used_thr, "order": int(order), "window": win_u},
        "fallback_used": bool(fallback_used and used_thr != thr_i),
        "legacy_fallback_used": False,
    }
    return df, info


from src.analytics.markov.states_model import (
    build_states_from_features,
    derive_matrix,
    states_stale,
    states_for,
)

# Grid config for nearest-threshold suggestion and coverage
import yaml as _yaml


def _load_features_for_page(ticker: str, features_root: Path | None = None):
    """Load features parquet for the UI with legacy schema handling.

    Returns (df, remapped) where remapped is True if 'ret' was mapped to 'ret_1d'.
    - Resolves features path relative to repo root by default (data/features/{ticker}.parquet).
    - Ensures 'date' is parsed to datetime (naive), sorted ascending, and duplicates by date are dropped keeping last.
    - Performs in-memory mapping; does not write files.
    """
    import pandas as pd

    root = features_root if features_root is not None else (ROOT / "data" / "features")
    p = root / f"{ticker}.parquet"
    if not p.exists():
        return None, False
    df = pd.read_parquet(p)
    # Normalize/ensure date column
    if "date" not in df.columns:
        df = df.reset_index()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
        df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    remapped = False
    if "ret_1d" not in df.columns and "ret" in df.columns:
        df = df.copy()
        df["ret_1d"] = df["ret"]
        remapped = True
    return df, remapped


def _format_missing_features_msg(ticker: str, features_path: "Path|str", required_cols: list[str]) -> str:
    """
    Pure helper (no Streamlit). Return a deterministic, multi-line message that:
    - Mentions the ticker and echoes features_path as given (Path or str is fine).
    - Lists required_cols (comma-separated).
    - Includes the exact CLI hints:
        python cli/mie.py build-features --mode full
        python cli/mie.py update-features --lookback 90
    - Ends with: "After building features, reload this page."
    No filesystem access, no logging, no imports beyond typing/pathlib if needed.
    """
    cols = ", ".join(required_cols or [])
    title = f"Features unavailable for {ticker}"
    details = f"Expected file: {features_path}"
    if cols:
        details = f"{details}\nRequired columns: {cols}"
    cli = (
        "python cli/mie.py build-features --mode full\n"
        "python cli/mie.py update-features --lookback 90"
    )
    ending = "After building features, reload this page."
    return f"{title}\n{details}\nCLI hint:\n{cli}\n{ending}"


def _format_missing_matrix_msg(ticker: str, state_mode: str, threshold_bps: int, order: int, window: str | None) -> str:
    """
    Pure helper (no Streamlit). Return a deterministic, multi-line message that:
    - Echoes params: ticker, state_mode, threshold_bps, order and window (if provided).
    - Provides a legacy-compatible CLI hint that STARTS with:
        python cli/mie.py build-markov --ticker {ticker} --order {order} --state-mode {state_mode} --threshold-bps {threshold_bps}
      If window is not None, append: --window {window}
      (Do NOT change the verb to ensure-markov-available here; tests expect build-markov.)
    - Ends with: "Re-run the command to generate the matrix, then reload this page."
    No filesystem access, no logging, no Streamlit.
    """
    params = f"ticker={ticker}, state_mode={state_mode}, threshold_bps={int(threshold_bps)}, order={int(order)}"
    if window is not None:
        params = f"{params}, window={window}"
    # Legacy-compatible build hint; omit --window to preserve compatibility with existing environments/tests
    cli = (
        f"python cli/mie.py build-markov --ticker {ticker} --order {int(order)} "
        f"--state-mode {state_mode} --threshold-bps {int(threshold_bps)}"
    )
    ending = "Re-run the command to generate the matrix, then reload this page."
    title = "Markov matrix unavailable"
    return f"{title}\nSelected params: {params}\nCLI hint:\n{cli}\n{ending}"


def _resolve_available_markov(base_dir: Path) -> dict:
    """Discover available Markov artifacts for a ticker.
    Returns dict: {state_mode, threshold_bps, orders: [K], paths: {states, metadata, matrices:{K:path}}}
    """
    meta_p = base_dir / "metadata.json"
    states_p = base_dir / "states.parquet"
    meta = read_json_safe(meta_p) or {}
    orders = []
    matrices = {}
    for K in range(1, 11):
        p = base_dir / f"matrix_order{K}.parquet"
        if p.exists():
            orders.append(K)
            matrices[K] = str(p)
    return {
        "state_mode": meta.get("state_mode"),
        "threshold_bps": meta.get("threshold_bps"),
        "orders": orders,
        "paths": {"states": str(states_p), "metadata": str(meta_p), "matrices": matrices},
    }


def _build_cli_for_combo(ticker: str, order: int, state_mode: str, thr_bps: int, window: str | None = None) -> str:
    """Build CLI command string for offline Markov analytics.

    Default (backward compatible): emit a build-markov command with no window flag:
        python cli/mie.py build-markov --ticker {ticker} --order {order} --state-mode {state_mode} --threshold-bps {thr_bps}

    If a window is provided, use the established windowed CLI (derive-markov-matrix) which supports --window:
        python cli/mie.py derive-markov-matrix --ticker {ticker} --state-mode {state_mode} --threshold-bps {thr_bps} --order {order} --window {window}

    Note: The ensure pathway is not used here.
    """
    if window is None:
        return (
            f"python cli/mie.py build-markov --ticker {ticker} "
            f"--order {order} --state-mode {state_mode} --threshold-bps {int(thr_bps)}"
        )
    # For windowed requests, leverage the derive-markov-matrix command which supports --window
    return (
        f"python cli/mie.py derive-markov-matrix --ticker {ticker} "
        f"--state-mode {state_mode} --threshold-bps {int(thr_bps)} --order {order} --window {window}"
    )


def _resolve_built_coverage(ticker: str, mode: str) -> dict:
    base = DATA / "analytics" / "markov" / ticker
    mode = _normalize_mode(mode)
    # thresholds with states
    thrs = []
    for p in (base.glob(f"states_thr*_{mode}.parquet")):
        try:
            thrs.append(int(p.name.split("_")[0].replace("states_thr", "")))
        except Exception:
            continue
    thrs = sorted(set(thrs))
    # orders available for current threshold by scanning matrices
    orders = set()
    mdir = base / "matrices" / mode
    if mdir.exists():
        for thr_dir in mdir.glob("thr*/"):
            try:
                tnum = int(thr_dir.name.replace("thr", ""))
            except Exception:
                continue
            for o in thr_dir.glob("order*/"):
                try:
                    K = int(o.name.replace("order", ""))
                    if any(o.glob("*.parquet")):
                        orders.add(K)
                except Exception:
                    continue
    return {"thresholds": thrs, "orders": sorted(orders)}


def _load_markov(ticker: str, order: int):
    base = DATA / "analytics" / "markov" / ticker
    mat = read_parquet_safe(base / f"matrix_order{order}.parquet")
    counts = read_parquet_safe(base / f"counts_order{order}.parquet")
    sweep = read_csv_safe(base / "order_sweep.csv")
    meta = read_json_safe(base / "metadata.json")
    return mat, counts, sweep, meta


def _derive_effective_params(meta: dict | None, controls: dict, available_orders: set[int]) -> tuple[int, str, int]:
    """Derive effective (order, state_mode, threshold_bps) with graceful fallbacks.
    Prefers control order if artifact exists; else meta order; else 1.
    State mode and threshold prefer controls if provided (truthy), else meta values, else defaults.
    """
    ctrl_order = int(controls.get("order", 1) or 1)
    ctrl_state_mode = controls.get("state_mode") or None
    ctrl_thr = controls.get("threshold_bps") or None

    meta_order = None
    meta_state_mode = None
    meta_thr = None
    if isinstance(meta, dict):
        meta_order = meta.get("order")
        meta_state_mode = meta.get("state_mode") or meta.get("mode")
        meta_thr = meta.get("threshold_bps") or meta.get("threshold")

    if ctrl_order in available_orders:
        eff_order = ctrl_order
    elif meta_order is not None:
        try:
            eff_order = int(meta_order)
        except Exception:
            eff_order = 1
    else:
        eff_order = 1

    eff_state_mode = (ctrl_state_mode or meta_state_mode or "binary")
    try:
        eff_thr = int(ctrl_thr if ctrl_thr is not None else (meta_thr if meta_thr is not None else 10))
    except Exception:
        eff_thr = 10
    return eff_order, eff_state_mode, eff_thr


def _headline_subline(ticker: str, dates: tuple[str, str], state_mode: str, thr_bps: int, order: int) -> str:
    return f"Ticker: {ticker} • Window: {dates[0]}→{dates[1]} • Source: offline • Params: state_mode={state_mode}, thr={thr_bps}bps, order={order}"


def _project_matrix_for_mode(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Return a view of matrix with proper columns per mode (binary drops Neutral)."""
    if df is None or df.empty:
        return df
    cols_tri = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in df.columns]
    if mode == "binary" and "mc_prob_neutral" in cols_tri:
        cols = ["mc_prob_up", "mc_prob_down"]
    else:
        cols = cols_tri
    keep = (["context"] if "context" in df.columns else []) + cols
    return df[keep].copy()


def _window_dates_from_features(ticker: str, window: str, features_dir: Path = DATA / "features") -> tuple[_dt.date, _dt.date]:
    p = features_dir / f"{ticker}.parquet"
    feats = read_parquet_safe(p)
    if feats is None or feats.empty or "date" not in feats.columns:
        today = _dt.date.today()
        return today - _dt.timedelta(days=365), today
    s = pd.to_datetime(feats["date"]).dt.date
    start_all, end_all = s.min(), s.max()
    if window in ("Max", None):
        return start_all, end_all
    win = str(window).upper().strip()
    if win in ("MAX", "", None):
        return start_all, end_all
    if win.endswith("Y") and win[:-1].isdigit():
        years = int(win[:-1])
        start = max(start_all, end_all - _dt.timedelta(days=365 * years))
        return start, end_all
    return start_all, end_all


def _build_context(states_df: pd.DataFrame, K: int, start: _dt.date, end: _dt.date) -> tuple[str | None, list[str]]:
    """Build G-N-R context string from last K states within [start,end]. Return (context_str, sequence_letters)."""
    if states_df is None or states_df.empty or "mc_state_today" not in states_df.columns:
        return None, []
    df = states_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[(df["date"] >= start) & (df["date"] <= end)].sort_values("date")
    if df.empty:
        return None, []
    # Map to letters U/N/D then to G/N/R for display
    letter_map = {"U": "G", "N": "N", "D": "R"}
    seq = [letter_map.get(str(x), None) for x in df["mc_state_today"].values.tolist()]
    seq = [x for x in seq if x is not None]
    if not seq:
        return None, []
    recent = seq[-K:]
    return "-".join(recent), recent


def _find_context_row(df: pd.DataFrame, ctx: str | None) -> pd.Series | None:
    """Robustly select the row for a given context.

    - If df is empty: return None
    - If ctx is falsy: return df.iloc[0]
    - Try exact index label match; if multiple rows, return the first
    - Else, if a 'context' column exists, try matching it; convert display ctx (G-N-R) to raw (UDN) before matching
    - On no match, return df.iloc[0]
    """
    if df is None or len(df) == 0:
        return None
    if not ctx:
        return df.iloc[0]
    # Try index label equality first
    try:
        if ctx in df.index:
            sel = df.loc[ctx]
            return sel.iloc[0] if isinstance(sel, pd.DataFrame) else sel
    except Exception:
        pass
    # Try matching via 'context' column with GNR->UDN conversion
    if "context" in df.columns:
        rev = {"G": "U", "N": "N", "R": "D"}
        parts = str(ctx).split("-")
        udn = "".join(rev.get(p, p) for p in parts if p)
        m = df[df["context"].astype(str) == udn]
        if not m.empty:
            return m.iloc[0]
    # Fallback to first row
    return df.iloc[0]


def _safe_pick_context_row(mat: pd.DataFrame, ctx: str | None):
    """Select a context row safely without triggering pandas truthiness.

    - If mat is None/empty -> None
    - If ctx is a non-empty string -> try _find_context_row, return Series if found
    - Else -> return first row (Series)
    """
    if mat is None or len(mat) == 0:
        return None
    if isinstance(ctx, str) and ctx:
        r = _find_context_row(mat, ctx)
        if isinstance(r, pd.Series):
            return r
    return mat.iloc[0]


def _most_likely_next(row: pd.Series, mode: str) -> tuple[str, float, float]:
    """Return (state_name, p_max, p_cont) where state_name in Green/Neutral/Red (or no Neutral for binary)."""
    if row is None:
        return ("", _np.nan, _np.nan)
    cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in row.index]
    if mode == "binary" and "mc_prob_neutral" in cols:
        cols = ["mc_prob_up", "mc_prob_down"]
    vals = row[cols].astype(float).values
    idx = int(vals.argmax()) if len(vals) else 0
    name = ["Green", "Neutral", "Red"][: len(cols)][idx]
    pmax = float(vals[idx])
    # continuation prob is staying in last state's color
    # infer last state from context row's context last letter
    last_letter = str(row.get("context", ""))[-1:]  # U/N/D
    cont_col = {"U": "mc_prob_up", "N": "mc_prob_neutral", "D": "mc_prob_down"}.get(last_letter)
    p_cont = float(row.get(cont_col, _np.nan)) if cont_col in row.index else _np.nan
    return name, pmax, p_cont


def _compute_multistep(pi_row: pd.Series, P_df: pd.DataFrame, horizons: list[int], mode: str) -> pd.DataFrame:
    """Compute pi * P^h for given horizons using offline K=1 matrix; return DataFrame with probs per horizon."""
    if pi_row is None or P_df is None or P_df.empty:
        return pd.DataFrame()
    # Build consistent column order
    cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in P_df.columns]
    if mode == "binary" and "mc_prob_neutral" in cols:
        cols = ["mc_prob_up", "mc_prob_down"]
    P = P_df[cols].to_numpy(dtype=float)
    # We need a square transition among states; assume rows are contexts for K=1: U,N,D
    # For display-only, approximate by averaging rows to get a generic transition among states
    trans = _np.nanmean(P, axis=0)
    # Construct a diagonal-like transition assuming independence (display-only)
    # Build a 3x3 or 2x2 with rows identical to trans
    n = len(cols)
    Pm = _np.tile(trans, (n, 1))
    # initial distribution from pi_row over cols
    pi = _np.array([float(pi_row.get(c, 0.0)) for c in cols])
    pi = pi / (pi.sum() if pi.sum() else 1.0)
    out = {}
    for h in horizons:
        # simple power by repeated multiplication (small n)
        Ph = Pm.copy()
        for _ in range(max(1, h - 1)):
            Ph = Ph @ Pm
        vec = pi @ Ph
        out[h] = {cols[i]: vec[i] for i in range(n)}
    return pd.DataFrame(out).T


def _make_matrix_table(df: pd.DataFrame):
    # Expect columns like mc_prob_up/mc_prob_neutral/mc_prob_down with context rows
    cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in df.columns]
    if not cols:
        return None
    sub = df[["context"] + cols].copy() if "context" in df.columns else df[cols].copy()
    # Map raw context (U/D/N) to display (G/R/N) with dashes
    def _ctx_disp(s: str) -> str:
        s = str(s or "")
        if not s:
            return s
        mp = {"U": "G", "N": "N", "D": "R"}
        parts = [mp.get(ch, ch) for ch in list(s)]
        return "-".join(parts)
    if "context" in sub.columns:
        sub["Context"] = sub["context"].astype(str).map(_ctx_disp)
        sub = sub.drop(columns=["context"])  # keep display-only label
    # Friendly headers
    rename = {
        "mc_prob_up": "Green (bullish)",
        "mc_prob_neutral": "Neutral",
        "mc_prob_down": "Red (bearish)",
    }
    sub = sub.rename(columns=rename)
    # Percent formatting
    for c in [v for k, v in rename.items() if v in sub.columns]:
        sub[c] = sub[c].map(fmt_percent_one_decimal)
    if "Context" in sub.columns:
        return sub.set_index("Context")
    return sub


def _plot_heatmap(df: pd.DataFrame, tokens: dict):
    cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in df.columns]
    if not cols:
        return None
    data = df[cols].astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(7, 3), dpi=140)
    mpl_style(fig, ax, tokens)
    colors = tokens["theme"]["colors"]
    # Map colors by column name so binary displays get bull/bear (no neutral)
    col_color = []
    for c in cols:
        if c == "mc_prob_up":
            col_color.append(colors.get("bull"))
        elif c == "mc_prob_neutral":
            col_color.append(colors.get("neutral"))
        elif c == "mc_prob_down":
            col_color.append(colors.get("bear"))
        else:
            col_color.append(colors.get("fg"))
    nr, nc = data.shape
    for i in range(nr):
        for j in range(nc):
            val = float(data[i, j])
            ax.add_patch(_Rect((j, i), 1, 1, color=col_color[j], alpha=min(max(val, 0.0), 1.0)))
    ax.set_xlim(0, nc)
    ax.set_ylim(nr, 0)
    ax.set_yticks([i + 0.5 for i in range(nr)])
    # Map y labels from raw context to display G-N-R with dashes
    def _ctx_disp(s: str) -> str:
        s = str(s or "")
        mp = {"U": "G", "N": "N", "D": "R"}
        return "-".join([mp.get(ch, ch) for ch in list(s)]) if s else s
    ylabels = []
    if "context" in df.columns:
        ylabels = [ _ctx_disp(s) for s in df["context"].astype(str).tolist() ]
    ax.set_yticklabels(ylabels)
    ax.set_xticks([k + 0.5 for k in range(nc)])
    xticks = []
    for c in cols:
        if c == "mc_prob_up":
            xticks.append("Green")
        elif c == "mc_prob_neutral":
            xticks.append("Neutral")
        elif c == "mc_prob_down":
            xticks.append("Red")
    ax.set_xticklabels(xticks)
    fig.tight_layout()
    return fig


@st.cache_data(show_spinner=False)
def _read_parquet_cached(path_str: str, size_bytes: int, mtime: float):
    """Cached parquet reader keyed by path+size+mtime. Returns a pandas DataFrame."""
    import pandas as pd
    return pd.read_parquet(path_str)


@st.cache_data(show_spinner=False)
def _read_matrix_cached(path_str: str, size_bytes: int, mtime: float):
    """Cached reader specifically for matrix parquet, keyed on filesystem attrs."""
    import pandas as pd
    return pd.read_parquet(path_str)


def _matrix_file_path(ticker: str, mode: str, thr: int, order: int, window: str) -> Path:
    win_key = window.upper() if window.upper() in {"1Y","2Y","5Y","10Y","20Y","MAX"} else "MAX"
    return DATA/"analytics"/"markov"/ticker/"matrices"/mode/f"thr{int(thr)}"/f"order{int(order)}"/f"{win_key}.parquet"


def _load_matrix_df(path: Path) -> pd.DataFrame:
    if not isinstance(path, Path):
        path = Path(path)
    if not path.exists() or os.path.getsize(path) <= 0:
        raise FileNotFoundError(str(path))
    st_stat = path.stat()
    return _read_matrix_cached(str(path), int(st_stat.st_size), float(st_stat.st_mtime))


@st.cache_data(show_spinner=False)
def _load_features_meta_cached(ticker: str, mtime: float | None, path_str: str) -> dict:
    """Load features metadata (for offline use) with graceful fallback to legacy schema.

    Returns metadata dict with keys:
    - exists (bool): file existence
    - has_ret_1d (bool): if features include 'ret_1d' column
    - path (str): resolved file path (for CLI hints)
    - mtime (float): file mtime (epoch seconds, float)
    - rows (int): row count (if known, else None)
    - cols (int): column count (if known, else None)
    - mode (str): state mode (if available, else None)
    - threshold_bps (int): threshold (if available, else None)
    - order (int): order (if available, else None)
    """
    import pandas as pd
    from os import PathLike

    fp = DATA / "features" / f"{ticker}.parquet"
    meta = {"exists": False, "has_ret_1d": False, "path": str(fp), "mtime": None}

    # Quick existence check
    if not fp.exists():
        return meta

    # Detailed metadata read
    try:
        # Legacy: direct read of features parquet to infer metadata
        df = pd.read_parquet(fp)
        meta["exists"] = True
        meta["mtime"] = fp.stat().st_mtime
        if "ret_1d" in df.columns:
            meta["has_ret_1d"] = True
        if "order" in df.columns and df["order"].dtype in ["int32", "int64"]:
            meta["order"] = int(df["order"].max())
        if "mode" in df.columns:
            meta["mode"] = str(df["mode"].iloc[0])
        if "threshold" in df.columns and df["threshold"].dtype in ["int32", "int64"]:
            meta["threshold_bps"] = int(df["threshold"].max())
        if "date" in df.columns and df["date"].dtype == "object":
            # coerce and check date parsing
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            if df["date"].notna().any():
                meta["rows"] = len(df)
                meta["cols"] = len(df.columns)
    except Exception:
        pass
    return meta


def _load_features_cached(arg):
    """Compatibility loader:
    - If called with a string ticker, return metadata dict for features file
    - If called with a Path-like, return (DataFrame, mtime_iso) for tests expecting the legacy behavior
    Read-only; never writes or computes features.
    """
    import pandas as pd
    from os import PathLike
    # ticker-style path
    if isinstance(arg, str):
        fp = DATA / "features" / f"{arg}.parquet"
        try:
            mtime = fp.stat().st_mtime if fp.exists() else None
        except Exception:
            mtime = None
        return _load_features_meta_cached(arg, mtime, str(fp))
    # Path-like behavior for legacy tests
    if isinstance(arg, (Path, PathLike)):
        fp = Path(arg)
        if not fp.exists() or os.path.getsize(fp) <= 0:
            raise FileNotFoundError(str(fp))
        st_stat = fp.stat()
        size_bytes = int(st_stat.st_size)
        mtime = float(st_stat.st_mtime)
        df = _read_parquet_cached(str(fp), size_bytes, mtime)
        # Validate 'date'
        if "date" not in df.columns:
            # do not fail hard; create a date index if any
            df = df.copy().reset_index()
        if not str(df["date"].dtype).startswith("datetime"):
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
        df = df.sort_values("date").reset_index(drop=True)
        # Ensure ret_1d exists as float
        if "ret_1d" in df.columns and not str(df["ret_1d"].dtype).startswith("float"):
            df = df.copy()
            df["ret_1d"] = pd.to_numeric(df["ret_1d"], errors="coerce").astype("float32")
        mtime_iso = pd.Timestamp.fromtimestamp(mtime, tz="UTC").isoformat()
        return df, mtime_iso
    # Fallback: treat as ticker string
    return _load_features_cached(str(arg))


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("📈 Markov Chain (discretized returns)")

    # Controls (lightweight)
    # Default ticker from config/tickers.yml if present
    def _default_ticker():
        try:
            cfg = Path("config/tickers.yml")
            if cfg.exists():
                data = yaml.safe_load(cfg.read_text())
                if isinstance(data, list):
                    for t in data:
                        if isinstance(t, str) and t.strip():
                            return t.strip().upper()
        except Exception:
            pass
        return "SPY"

    # Session state defaults and transient apply flags (set BEFORE widget creation)
    st.session_state.setdefault("mk_ticker", _default_ticker())
    st.session_state.setdefault("mk_order", 1)
    st.session_state.setdefault("mk_state_mode", "tri")
    st.session_state.setdefault("mk_threshold", 10)
    st.session_state.setdefault("mk_window", "1Y")

    # Apply transient threshold preset from previous run (if any), then clear flags
    if st.session_state.get("mk_apply_threshold"):
        new_thr = int(st.session_state.get("mk_apply_threshold_value", st.session_state.get("mk_threshold", 10)))
        st.session_state["mk_threshold"] = new_thr
        st.session_state.pop("mk_apply_threshold", None)
        st.session_state.pop("mk_apply_threshold_value", None)

    st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], key="mk_ticker")
    ticker = _get_ticker_from_state("SPY")
    assert isinstance(ticker, str) and ticker, "ticker must be a string symbol"
    # Optional: assert ticker in supported set (from config if desired)
    raw_window = st.sidebar.selectbox("Time range", ["1Y", "2Y", "5Y", "10Y", "20Y", "Max", "Custom"], index=0, key="mk_window")
    window = _normalize_window_value(raw_window)
    raw_norm = str(raw_window).upper().strip()
    if window == "1Y" and raw_norm not in {"1Y","1"}:
        st.caption("Unsupported window selection; fell back to 1Y.")
    ctrl_state_mode = st.sidebar.selectbox("State mode", ["binary", "tri"], key="mk_state_mode")
    ctrl_thr = st.sidebar.number_input("Threshold (bps)", min_value=0, max_value=1000, step=5, key="mk_threshold")
    ctrl_order = st.sidebar.slider("Order", min_value=1, max_value=4, key="mk_order")
    horizons = st.sidebar.multiselect("Horizons (days)", options=list(range(1, 21)), default=[1, 2, 3, 4])

    if st.sidebar.button("🔄 Clear data cache & reload", width="content"):
        st.cache_data.clear()
        st.rerun()

    # Guard rendering until a valid ticker and state mode are selected
    try:
        mode_ok = _normalize_mode(ctrl_state_mode) in {"binary", "tri"}
    except Exception:
        mode_ok = False
    ticker_ok = isinstance(ticker, str) and bool(ticker.strip())
    if not (ticker_ok and mode_ok):
        st.info("Select a ticker and state mode to display analysis.")
        return

    # Load grid thresholds for nearest suggestion
    try:
        grid = _yaml.safe_load((Path("config")/"analytics_grid.yml").read_text())
        grid_thrs = sorted([int(x) for x in grid.get("thresholds_bps", [])])
    except Exception:
        grid_thrs = [10]
    base = _build_markov_base_path(ticker)
    coverage = _resolve_built_coverage(ticker, ctrl_state_mode)

    # Effective params follow the controls; if exact artifact is missing or metadata mismatches, we warn and do not display stale data.
    eff_order, eff_state_mode, eff_thr = ctrl_order, ctrl_state_mode, int(ctrl_thr)

    # Ensure features exist (offline) with ret_1d; read-only metadata
    meta = _load_features_cached(ticker)
    feat_path = Path(meta.get("path", DATA/"features"/f"{ticker}.parquet"))
    if not meta.get("exists", False) or meta.get("has_ret_1d") is False:
        req = ["ret_1d"]
        msg = _format_missing_features_msg(ticker, feat_path, req)
        DataStatus(msg, "warning")
        return
    # Precompute feature-based range for header fallback
    fstart, fend = _window_dates_from_features(ticker, window)

    # Determine normalized window key once for downstream path resolution
    win_key = window if window in {"1Y","2Y","5Y","10Y","20Y","MAX"} else "MAX"

    # Read-only: do not compute in UI; only attempt to load derived/cached matrix, else show CLI hint
    try:
        mat, mat_info = _load_matrix_for_selection(ticker, eff_state_mode, int(eff_thr), int(eff_order), win_key, allow_fallback=False)
    except Exception:
        # Header lines even if matrix missing
        # Determine last updated as max of features mtime and existing matrix (if present)
        last_iso = meta.get("mtime")
        try:
            mp = _matrix_exact_path(ticker, eff_state_mode, eff_thr, eff_order, win_key)
            if Path(mp).exists():
                mtime2 = pd.Timestamp.fromtimestamp(Path(mp).stat().st_mtime, tz="UTC").isoformat()
                # pick the later iso by comparison of pandas Timestamps
                if last_iso is None or pd.Timestamp(mtime2) > pd.Timestamp(last_iso):
                    last_iso = mtime2
        except Exception:
            pass
        # Use feature-based window dates for header when matrix is unavailable
        d0, d1 = (fstart.isoformat(), fend.isoformat())
        st.caption(f"Data set for {ticker}: {d0} – {d1}.  Last updated: {last_iso}")
        mode_name = eff_state_mode
        st.caption(f"Ticker: {ticker} • Time range: {window.upper()} • Source: offline • State mode: {mode_name} • Threshold: {eff_thr}bps • Order: {eff_order}")
        # Use ensure-markov-available hint with requested params
        ensure_cli = (
            f"python cli/mie.py ensure-markov-available --ticker {ticker} "
            f"--order {eff_order} --state-mode {eff_state_mode} --threshold-bps {int(eff_thr)} --window {win_key}"
        )
        DataStatus(
            "Markov matrix unavailable\nCLI hint:\n" + ensure_cli + "\nRe-run the command to generate the matrix, then reload this page.",
            "warning",
        )
        st.dataframe(pd.DataFrame())
        return

    # Compute dates window
    fstart, fend = _window_dates_from_features(ticker, window)
    # load states-for for context determination
    try:
        s_for = states_for(ticker, eff_thr, eff_state_mode)
    except Exception:
        s_for = None
    if s_for is not None and not s_for.empty and "date" in s_for.columns:
        sdates = pd.to_datetime(s_for["date"]).dt.date
        astart, aend = sdates.min(), sdates.max()
        d0 = max(fstart, astart)
        d1 = min(fend, aend)
        dates = (d0.isoformat(), d1.isoformat())
    else:
        dates = (fstart.isoformat(), fend.isoformat()) if isinstance(fstart, _dt.date) and isinstance(fend, _dt.date) else ("unknown", "unknown")

    # Two-line human-friendly header under title
    # Last updated is the later of features mtime and matrix file mtime (if present)
    last_iso = meta.get("mtime")
    try:
        mp = mat_info["path"] if 'mat_info' in locals() else _matrix_exact_path(ticker, eff_state_mode, eff_thr, eff_order, win_key)
        if Path(mp).exists():
            mtime2 = pd.Timestamp.fromtimestamp(Path(mp).stat().st_mtime, tz="UTC").isoformat()
            if last_iso is None or pd.Timestamp(mtime2) > pd.Timestamp(last_iso):
                last_iso = mtime2
    except Exception:
        pass
    st.caption(f"Data set for {ticker}: {dates[0]} – {dates[1]}.  Last updated: {last_iso}")
    mode_name = eff_state_mode
    st.caption(f"Ticker: {ticker} • Time range: {window.upper()} • Source: offline • State mode: {mode_name} • Threshold: {eff_thr}bps • Order: {eff_order}")
    # Small features status line
    rows = meta.get("rows"); cols = meta.get("cols"); mti = meta.get("mtime")
    if rows is not None or mti is not None:
        st.caption(f"Features: rows={rows if rows is not None else '?'} • cols={cols if cols is not None else '?'} • mtime={mti if mti else '?'}")

    # Project matrix per mode
    mat_mode = _project_matrix_for_mode(mat, eff_state_mode)
    # Validate row sums approx 1
    prob_cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in mat_mode.columns]
    if prob_cols:
        sums = mat_mode[prob_cols].astype(float).sum(axis=1)
        if (sums - 1.0).abs().max() > 1e-3:
            DataStatus("warning: matrix rows do not sum to ~1.0", "warning")

    # Table
    tbl = _make_matrix_table(mat_mode)
    if tbl is not None and not tbl.empty:
        st.dataframe(tbl)
    else:
        DataStatus("offline data present, but no transition columns to show", "warning")

    # Heatmap
    fig = _plot_heatmap(mat_mode, tokens)
    if fig is not None:
        plot_mpl(fig, caption="Transition probabilities (row-wise)")

    # Temporary Binary Threshold Debug panel
    if DEBUG_BINARY_THRESHOLD and _normalize_mode(eff_state_mode) == "binary":
        try:
            pth = mat_info.get("path")
            stat = Path(pth).stat()
            size = int(stat.st_size)
            mtime = float(stat.st_mtime)
            # Quick checksum: sha1 of file bytes (streamed)
            sha1 = _hashlib.sha1()
            with open(pth, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha1.update(chunk)
            checksum = sha1.hexdigest()[:12]
            # First row (raw matrix) rounded to 3 decimals
            first_row = None
            cols_dbg = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in mat.columns]
            if not cols_dbg and not mat.empty:
                cols_dbg = [c for c in mat.columns if c.startswith("mc_prob_")]
            if not mat.empty and cols_dbg:
                r0 = mat.iloc[0][cols_dbg].astype(float).round(3).to_dict()
                first_row = r0
            # Active cache key
            cache_key = (ticker, _normalize_mode(eff_state_mode), int(eff_thr), int(eff_order), win_key)
            legacy_fallback = bool(mat_info.get("legacy_fallback_used", False))
            with st.expander("Binary Threshold Debug", expanded=False):
                st.text("\n".join([
                    f"resolved_path: {pth}",
                    f"fingerprint: size={size} mtime={mtime:.0f} sha1={checksum}",
                    f"first_row: {first_row}",
                    f"cache_key: {cache_key}",
                    f"legacy_fallback_used: {legacy_fallback}",
                ]))
            # Warn if checksums identical across threshold changes
            prev = st.session_state.get("mk_debug_prev")
            cur_sig = {"thr": int(eff_thr), "checksum": checksum}
            if prev and prev.get("thr") != cur_sig["thr"] and prev.get("checksum") == cur_sig["checksum"]:
                DataStatus("Matrix files for previous and current thresholds appear byte-identical; check offline build.", "warning")
            st.session_state["mk_debug_prev"] = cur_sig
        except Exception:
            pass

    # Context-aware summary
    ctx_gnr, seq = _build_context(s_for.rename(columns={"state": "mc_state_today"}) if s_for is not None else None, eff_order, _dt.date.fromisoformat(dates[0]), _dt.date.fromisoformat(dates[1]))
    row = _safe_pick_context_row(mat_mode, _as_context_key(ctx_gnr))
    state_name, pmax, pcont = _most_likely_next(row, eff_state_mode)
    if ctx_gnr and state_name:
        colors = tokens["theme"]["colors"]
        col_map = {"Green": colors.get("bull"), "Neutral": colors.get("neutral"), "Red": colors.get("bear")}
        colored = f"<span style='color:{col_map.get(state_name, colors.get('fg'))}'>{state_name}</span>"
        last_state = seq[-1] if seq else ""
        st.markdown(
            f"<div class='small'>Given previous context: <span class='accent'>{ctx_gnr}</span>, most likely next day is {colored} ({fmt_percent_one_decimal(pmax)}). "
            f"Continuation (stay {last_state}) = {fmt_percent_one_decimal(pcont)}; switch = {fmt_percent_one_decimal(1 - pcont if pcont==pcont else 0)}.</div>",
            unsafe_allow_html=True,
        )

    # One-step next-state table for active context
    if row is not None:
        cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in row.index]
        if eff_state_mode == "binary" and "mc_prob_neutral" in cols:
            cols = ["mc_prob_up", "mc_prob_down"]
        vals = [fmt_percent_one_decimal(float(row[c])) for c in cols]
        names = ["Green (bullish)", "Neutral", "Red (bearish)"][: len(cols)]
        st.dataframe(pd.DataFrame([vals], columns=names))
        st.caption(f"Given {ctx_gnr}, tomorrow is most likely {state_name} ({fmt_percent_one_decimal(pmax)}).")

    # recompute k=1 from cache for current window to drive multi-step
    try:
        mat_k1, _mi2 = _load_matrix_for_selection(
            ticker,
            eff_state_mode,
            int(eff_thr),
            1,
            window if window in {"1Y","2Y","5Y","10Y","20Y","MAX"} else "MAX",
            allow_fallback=False,
        )
    except Exception:
        mat_k1 = None
    if mat_k1 is not None and not mat_k1.empty:
        mat_k1m = _project_matrix_for_mode(mat_k1, eff_state_mode)
        pi_df = _find_context_row(mat_k1m, ctx_gnr)
        if pi_df is None and mat_k1m is not None and not mat_k1m.empty:
            pi_df = mat_k1m.iloc[0]
        pi_df = _safe_pick_context_row(mat_k1m, _as_context_key(ctx_gnr))
        mult = _compute_multistep(pi_df, mat_k1m, horizons, eff_state_mode)
        if not mult.empty:
            # format and display
            disp = mult.rename(columns={
                "mc_prob_up": "Green (bullish)",
                "mc_prob_neutral": "Neutral",
                "mc_prob_down": "Red (bearish)",
            }).applymap(fmt_percent_one_decimal)
            st.dataframe(disp)


def _build_markov_base_path(ticker: str) -> Path:
    """Build DATA/analytics/markov/{ticker} with type checks.

    Raises:
        ValueError: if ticker is not a string symbol.
    """
    if not isinstance(ticker, str):
        raise ValueError("ticker must be a string symbol")
    base = DATA / "analytics" / "markov" / ticker
    assert base.is_absolute()
    return base


if __name__ == "__main__":
    main()
