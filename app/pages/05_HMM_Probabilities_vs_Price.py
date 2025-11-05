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
from app.ui.components import read_parquet_safe, fmt_percent_one_decimal

DATA = Path("data")


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Regime Probabilities vs Ticker")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    hmm = DATA / "analytics" / "hmm" / ticker
    probs = read_parquet_safe(hmm / "hmm_probs.parquet")

    if probs is None or probs.empty:
        DataStatus(f"offline data not found: {hmm / 'hmm_probs.parquet'}", "warning")
        return

    # Recent snapshot
    cols = [c for c in ["hmm_prob_bull", "hmm_prob_neutral", "hmm_prob_bear"] if c in probs.columns]
    if cols:
        last = probs[cols].iloc[-1]
        st.caption("Current probabilities — " + ", ".join([f"{c.split('_')[-1].capitalize()} {fmt_percent_one_decimal(last[c])}" for c in cols]))
    st.line_chart(probs.set_index("date")[cols].tail(500))


if __name__ == "__main__":
    main()

