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
from app.ui.components import read_parquet_safe, read_json_safe

DATA = Path("data")


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Downtrend Confirmation Score")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    p = DATA / "analytics" / "downtrend" / ticker / "score.json"
    js = read_json_safe(p)
    if not js:
        DataStatus("offline data not found: downtrend score", "warning")
        return
    st.json(js)


if __name__ == "__main__":
    main()

