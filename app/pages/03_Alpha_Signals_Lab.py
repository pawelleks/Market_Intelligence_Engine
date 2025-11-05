# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]  # parent of "app"
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

from pathlib import Path
import pandas as pd
import streamlit as st

from app.ui.theme import get_tokens, css_inject
from app.ui.components import SectionHeader, Card, SummaryBox, DataStatus

DATA_DIR = Path("data")

@st.cache_data(ttl=600)
def _read_parquet(path: Path):
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def render():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Alpha Signals Lab")
    ticker = st.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)

    SectionHeader("Downtrend Confirmation Score", None)

    def body_downtrend():
        p = DATA_DIR / "signals" / ticker / "downtrend_score.parquet"
        df = _read_parquet(p)
        if df is None:
            DataStatus("Downtrend score not found", "warn")
            return
        st.line_chart(df.set_index("date").iloc[-200:])
        SummaryBox("Placeholder: downtrend commentary.")

    Card("Downtrend Score", None, body_downtrend)

    SectionHeader("Seasonality Snapshot", None)

    def body_seasonality():
        DataStatus("Seasonality placeholder", "info")
        SummaryBox("Placeholder: seasonality snapshot coming soon.")

    Card("Seasonality", None, body_seasonality)


if __name__ == "__main__":
    render()
