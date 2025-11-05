# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import streamlit as st
from pathlib import Path

from app.ui.theme import css_inject, get_tokens
from app.ui.components import SectionHeader, DataStatus
from app.ui.components import read_parquet_safe

DATA = Path("data")


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Markov Predictive Bands")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    base = DATA / "analytics" / "markov" / ticker
    bands = read_parquet_safe(base / "predictive_bands.parquet")

    if bands is None or bands.empty:
        DataStatus("not available (offline)", "warning")
        return

    st.dataframe(bands.head())


if __name__ == "__main__":
    main()

