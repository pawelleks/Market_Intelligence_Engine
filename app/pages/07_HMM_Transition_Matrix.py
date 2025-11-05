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
from app.ui.components import read_parquet_safe

DATA = Path("data")


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("HMM transition matrix (daily transition probabilities)")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    hmm = DATA / "analytics" / "hmm" / ticker
    metrics = read_parquet_safe(hmm / "hmm_metrics.parquet")

    if metrics is None or metrics.empty:
        DataStatus(f"offline data not found: {hmm / 'hmm_metrics.parquet'}", "warning")
        return

    st.dataframe(metrics.head())
    st.caption("Placeholder: show From→To probabilities as percentages with expected durations.")


if __name__ == "__main__":
    main()

