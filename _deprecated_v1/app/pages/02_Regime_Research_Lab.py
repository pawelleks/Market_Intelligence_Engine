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

    st.title("Regime Research Lab")
    ticker = st.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)

    hmm_dir = DATA_DIR / "analytics" / "hmm" / ticker
    mk_dir = DATA_DIR / "analytics" / "markov" / ticker

    # HMM Model Explorer
    SectionHeader("HMM Model Explorer", None)

    def body_hmm():
        metrics = _read_parquet(hmm_dir / "hmm_metrics.parquet")
        probs = _read_parquet(hmm_dir / "hmm_probs.parquet")
        if metrics is None or probs is None:
            DataStatus("HMM metrics/probs not found", "warn")
            return
        st.dataframe(metrics.head())
        st.line_chart(probs.set_index("date").dropna().iloc[-200:])
        SummaryBox("Placeholder: analysis summary.")

    Card("HMM Explorer", None, body_hmm)

    # Markov Chain Explorer
    SectionHeader("Markov Chain Explorer", None)

    k = st.radio("Order K", [1, 2, 3, 4], horizontal=True)

    def body_markov():
        p = mk_dir / f"matrix_order{k}.parquet"
        df = _read_parquet(p)
        if df is None:
            DataStatus(f"matrix_order{k}.parquet not found", "warn")
            return
        st.dataframe(df.head())
        SummaryBox("Placeholder: next-state insights.")

    Card("Markov Explorer", f"Matrix K={k}", body_markov)


if __name__ == "__main__":
    render()
