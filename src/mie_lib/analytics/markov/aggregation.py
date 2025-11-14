"""Compatibility shim for legacy imports.

This module provides functions expected by legacy pages/tests such as
`aggregate_to_state_matrix` and `select_context_row` by forwarding calls to
current implementations (states_model/markov_engine or helpers).

No analytics math is implemented here; these are thin delegates.
"""
from __future__ import annotations

from typing import Iterable
import pandas as pd
import numpy as np
import importlib

# Optionally load canonical helpers if available, without raising import-time errors
_compute_multi_horizon_probs = None
_select_context_row = None
try:  # pragma: no cover - best-effort optional import
    _helpers = importlib.import_module("mie_lib.analytics.markov.helpers")
    _compute_multi_horizon_probs = getattr(_helpers, "compute_multi_horizon_probs", None)
    _select_context_row = getattr(_helpers, "select_context_row", None)
except Exception:
    pass


def aggregate_to_state_matrix(df: pd.DataFrame, mode: str = "tri") -> pd.DataFrame:
    """Aggregate context-level matrix to state-level (U/N/D rows).

    Input df must have columns:
      - 'context'
      - probability columns: tri -> mc_prob_up, mc_prob_neutral, mc_prob_down
                               binary -> mc_prob_up, mc_prob_down
    For order=1 where 'context' is a single raw code (e.g., 'U'/'N'/'D'),
    this naturally becomes state-level. For higher orders, rows are grouped
    by their LAST raw state character.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["context", "mc_prob_up", "mc_prob_neutral", "mc_prob_down"]) if mode == "tri" else pd.DataFrame(columns=["context", "mc_prob_up", "mc_prob_down"])
    tri = (mode == "tri")
    cols = ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if tri else ["mc_prob_up", "mc_prob_down"]
    for c in cols:
        if c not in df.columns:
            raise KeyError(f"missing column {c} in matrix df")
    # Determine last-state key per context
    ctx = df["context"].astype(str)
    last = ctx.str.split("-").str[-1]  # handle verbose like 'U-N-D'
    last = last.str[-1]  # compact to last raw code
    tmp = df.copy()
    tmp["_last"] = last
    # Average probabilities per last state
    agg = tmp.groupby("_last", as_index=False)[cols].mean()
    # Build canonical state-level frame ordered by universe
    if tri:
        universe = ["U", "N", "D"]
        base = pd.DataFrame({"context": universe})
        out = base.merge(agg.rename(columns={"_last": "context"}), on="context", how="left").fillna(0.0)
    else:
        universe = ["U", "D"]
        base = pd.DataFrame({"context": universe})
        out = base.merge(agg.rename(columns={"_last": "context"}), on="context", how="left").fillna(0.0)
    return out


def select_context_row(df: pd.DataFrame, compact_context: str):
    """Compatibility wrapper. Return (row_series, used_label).

    If a canonical `_select_context_row` exists in helpers, delegate to it;
    otherwise implement a minimal fuzzy matcher that tries compact and verbose
    labels and progressively shortens the context until a row is found.
    """
    if df is None or df.empty:
        return None, None
    if callable(_select_context_row):
        try:
            return _select_context_row(df, compact_context)
        except Exception:
            pass
    # Fallback fuzzy selection
    labels = list(df["context"].astype(str)) if "context" in df.columns else list(df.index.astype(str))
    ctx = str(compact_context or "").upper().strip()
    # Try exact, verbose, then shorten
    def to_verbose(comp: str) -> str:
        # Map 'GRN' -> 'G-R-N' then normalize to raw 'U/N/D' domain not needed for matching
        return "-".join(list(comp))
    candidates = [ctx, to_verbose(ctx)]
    for cand in candidates:
        if cand in labels:
            row = df[df["context"].astype(str) == cand].iloc[0] if "context" in df.columns else df.loc[cand]
            return row, cand
    for k in range(len(ctx) - 1, 0, -1):
        sub = ctx[-k:]
        for cand in [sub, to_verbose(sub)]:
            if cand in labels:
                row = df[df["context"].astype(str) == cand].iloc[0] if "context" in df.columns else df.loc[cand]
                return row, cand
    return None, None


# Optional re-export for horizons if helper exists

def compute_multi_horizon_probs(df: pd.DataFrame, context_label: str, horizons: Iterable[int], mode: str = "binary") -> pd.DataFrame:
    if callable(_compute_multi_horizon_probs):
        fn = _compute_multi_horizon_probs  # type: ignore[assignment]
        return fn(df, context_label, horizons, mode=mode)  # type: ignore[misc]
    # Minimal inline computation using numpy matrix powers as fallback
    P_df = aggregate_to_state_matrix(df, mode=mode)
    if mode == "tri":
        P = P_df[["mc_prob_up", "mc_prob_neutral", "mc_prob_down"]].values
        idx = {"U": 0, "N": 1, "D": 2}
    else:
        P = P_df[["mc_prob_up", "mc_prob_down"]].values
        idx = {"U": 0, "D": 1}
    # Start distribution from last-state of context_label
    last = str(context_label or "U").upper()[-1]
    p0 = np.zeros(P.shape[0]); p0[idx.get(last, 0)] = 1.0
    out = {}
    for h in sorted(set(int(h) for h in horizons)):
        if h <= 0:
            continue
        if h == 1:
            p = p0 @ P
        else:
            p = p0 @ np.linalg.matrix_power(P, h)
        if mode == "tri":
            out[h] = {"mc_prob_up": p[0], "mc_prob_neutral": p[1], "mc_prob_down": p[2]}
        else:
            out[h] = {"mc_prob_up": p[0], "mc_prob_down": p[1]}
    return pd.DataFrame.from_dict(out, orient="index").sort_index()


__all__ = [
    "aggregate_to_state_matrix",
    "select_context_row",
    "compute_multi_horizon_probs",
]
