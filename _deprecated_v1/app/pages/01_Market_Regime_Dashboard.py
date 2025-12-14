# --- path shim: ensure project root on sys.path for `from mie_lib...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]  # parent of "app"
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import os
from pathlib import Path
import math
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import json

# --- START PATH FIX ---
# Import canonical path functions and constants from the core library
from mie_lib.utils.paths import (
    markov_out_dir,
    hmm_out_dir,
    features_parquet_path,
    markov_matrix_path_flat,
    DATA_DIR # Imported for compatibility with other paths
)

# Removed: ROOT = Path(__file__).resolve().parents[2]
# Removed: DATA_DIR = ROOT / "data"
# --- END PATH FIX ---

from app.ui.theme import get_tokens, css_inject, mpl_style, fmt_pct
from app.ui.theme import get_metric_labels, color_for_status
from app.ui.components import SectionHeader, Card, SummaryBox, ExpandableChart, DataStatus, DownloadRow
from app.ui.components import plot_mpl, apply_friendly_labels, fmt_percent_two_decimals

# ... (Helper functions _read_parquet, _freshness_text, etc. are unchanged) ...

# ===== HMM chart helpers =====

def load_price_and_hmm(ticker: str):
    """Load features price, hmm states, and optional probs; merge by date.
    Returns (merged_df, probs_df_or_none)
    merged_df columns: date, price, hmm_state_name
    If probs present, columns hmm_prob_bull/hmm_prob_bear/(neutral) are merged as well.
    """
    # --- PATH FIX APPLIED HERE ---
    feat_p = features_parquet_path(ticker)
    hmm_dir = hmm_out_dir(ticker)
    states_p = hmm_dir / "hmm_states.parquet" # Note: This states_p is still manual, should be fixed in the HMM file later
    probs_p = hmm_dir / "hmm_probs.parquet"   # This probs_p is still manual, should be fixed in the HMM file later
    # --- END PATH FIX ---

    df_feat = _read_parquet(feat_p)
    df_states = _read_parquet(states_p)
    if df_feat is None or df_states is None:
        return None, None
    # ... (rest of function unchanged) ...
    return merged.reset_index(drop=True), df_probs


# ... (draw_hmm_regimes_chart and _summary_text unchanged) ...

def render():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Market Regime Dashboard")

    # Controls
    ticker = st.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    history = st.selectbox("History", ["1Y", "3Y", "5Y", "Max"], index=2)

    # --- PATH FIX APPLIED HERE ---
    hmm_dir = hmm_out_dir(ticker)
    mk_dir = markov_out_dir(ticker)
    # --- END PATH FIX ---

    # Section A: SPY Price with HMM Regimes
    SectionHeader("SPY Price with HMM Regimes", f"Ticker={ticker}, Window={history}")

    def body_hmm():
        # Robust loads: states, probs, metadata (independent of UI history)
        meta = _read_json(hmm_dir / "hmm_metadata.json")
        df_states = _read_parquet(hmm_dir / "hmm_states.parquet")
        df_probs = _read_parquet(hmm_dir / "hmm_probs.parquet")
        if df_states is None or df_states.empty:
            # Show single info with CLI
            years_map = {"1Y": 1, "3Y": 3, "5Y": 5, "Max": 5}
            years = years_map.get(history, 5)
            # CLI path remains the same
            st.info(f"HMM not found. Build via: python cli/mie.py build-hmm --ticker {ticker} --states 2 --window-years {years}")
            return
        # ... (rest of function unchanged) ...
            # Build price series from features for the same ticker
            # --- PATH FIX APPLIED HERE ---
            feat_p = features_parquet_path(ticker) # Use canonical path function
            # --- END PATH FIX ---
            feats = _read_parquet(feat_p)
            # ... (rest of function unchanged) ...

    Card("HMM Regimes", f"Files: hmm_states.parquet, hmm_probs.parquet", body_hmm)

    # Section B: Markov Order Sweep — Latest Context
    SectionHeader("Markov Order Sweep — Latest Context", None)

    def body_sweep():
        labels = get_metric_labels()
        # --- PATH FIX APPLIED HERE ---
        df_sweep = _read_csv(mk_dir / "order_sweep.csv")
        # --- END PATH FIX ---
        if df_sweep is None or df_sweep.empty:
            DataStatus("Markov order_sweep.csv not found. Build via: python cli/mie.py build-markov-sweep --ticker {ticker} --orders 1,2,3,4 --state-mode tri --threshold-bps 10", "info")
            return
        # ... (rest of function unchanged) ...

    Card("Order Sweep", "Latest context probability snapshot", body_sweep)

    # Section C: One-step Next-State Table
    SectionHeader("One-step Next-State Table", None)

    def body_one_step():
        labels = get_metric_labels()
        # --- PATH FIX APPLIED HERE ---
        p = markov_matrix_path_flat(ticker, order=1) # Use canonical path function
        # --- END PATH FIX ---
        df = _read_parquet(p)
        if df is None or df.empty:
            DataStatus(
                f"matrix_order1.parquet not found. Build via: python cli/mie.py build-markov --ticker {ticker} --order 1 --state-mode tri --threshold-bps 10",
                "info",
            )
            return
        # ... (rest of function unchanged) ...

    Card("One-step Markov Matrix", "K=1", body_one_step)

    # Freshness line
    st.markdown(
        f"<div class='muted'>{_freshness_text([hmm_dir / 'hmm_states.parquet', hmm_dir / 'hmm_probs.parquet', mk_dir / 'order_sweep.csv', markov_matrix_path_flat(ticker, order=1)])}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    render()