# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import streamlit as st
from pathlib import Path
import pandas as pd

from app.ui.theme import css_inject, get_tokens
from app.ui.components import SectionHeader, DataStatus
from app.ui.components import read_parquet_safe, read_csv_safe, fmt_percent_one_decimal

DATA = Path("data")


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Key Probability Gauges")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)

    # Try Markov next-state
    base = DATA / "analytics" / "markov" / ticker
    sweep = read_csv_safe(base / "order_sweep.csv")
    if sweep is not None and not sweep.empty:
        last = sweep.sort_values("order").iloc[-1]
        cols = [c for c in ["mc_prob_up_next", "mc_prob_neutral_next", "mc_prob_down_next"] if c in sweep.columns]
        if cols:
            st.write("Markov next-day:")
            st.write({c: fmt_percent_one_decimal(last[c]) for c in cols})
    else:
        DataStatus("offline Markov probabilities not available", "warning")

    # Try HMM latest
    probs = read_parquet_safe(DATA / "analytics" / "hmm" / ticker / "hmm_probs.parquet")
    if probs is not None and not probs.empty:
        cols2 = [c for c in ["hmm_prob_bull", "hmm_prob_neutral", "hmm_prob_bear"] if c in probs.columns]
        if cols2:
            st.write("HMM today:")
            st.write(probs[cols2].tail(1).to_dict("records")[0])
    else:
        DataStatus("offline HMM probabilities not available", "warning")


if __name__ == "__main__":
    main()

