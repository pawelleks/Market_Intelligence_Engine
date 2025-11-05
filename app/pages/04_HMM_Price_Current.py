# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import streamlit as st
from pathlib import Path
import matplotlib.pyplot as plt

from app.ui.theme import css_inject, get_tokens, color_for_status, mpl_style
from app.ui.components import DataStatus, plot_mpl
from app.ui.components import read_parquet_safe, read_json_safe

DATA = Path("data")


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("SPY Price with HMM-Detected Regimes")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    # Standardized path: win5y/states{N}
    base = DATA / "analytics" / "hmm" / ticker
    win_dir = base / "win5y"
    # Try 3-state first, then 2-state for UI; in future add a toggle
    hmm_dir = win_dir / "states3"
    if not (hmm_dir / "hmm_states.parquet").exists():
        hmm_dir = win_dir / "states2"

    states = read_parquet_safe(hmm_dir / "hmm_states.parquet")
    probs = read_parquet_safe(hmm_dir / "hmm_probs.parquet")
    meta = read_json_safe(hmm_dir / "hmm_metadata.json")

    if states is None or states.empty:
        DataStatus(f"offline data not found: {hmm_dir / 'hmm_states.parquet'}", "warning")
        return

    feats = read_parquet_safe(DATA / "features" / f"{ticker}.parquet")
    if feats is None or feats.empty:
        DataStatus(f"offline data not found: {DATA / 'features' / f'{ticker}.parquet'}", "warning")
        return

    # Build price robustly: prefer adj_close, else close; else error
    cols_lc = {c.lower(): c for c in feats.columns}
    price_src = cols_lc.get("adj_close") or cols_lc.get("adj close") or cols_lc.get("close")
    if not price_src:
        st.error("Price column not found in features (expected 'Adj Close' or 'Close'). Please rebuild features.")
        return
    price = feats[["date", price_src]].rename(columns={price_src: "price"})
    df = price.merge(states[["date", "hmm_state_name"]], on="date", how="left").dropna()

    # Plot
    fig, ax = plt.subplots(figsize=(7, 3), dpi=140)
    mpl_style(fig, ax, tokens)
    ax.plot(df["date"], df["price"], color=color_for_status("neutral"))
    def col(s: str):
        return color_for_status("bull" if s == "Bull" else ("bear" if s == "Bear" else "neutral"))
    # simple spans
    last_state, start = None, None
    for d, sname in zip(df["date"], df["hmm_state_name"].fillna("Neutral")):
        if last_state is None:
            last_state, start = sname, d
        elif sname != last_state:
            ax.axvspan(start, d, color=col(last_state), alpha=0.08)
            last_state, start = sname, d
    if last_state is not None:
        ax.axvspan(start, df["date"].iloc[-1], color=col(last_state), alpha=0.08)
    fig.tight_layout()
    plot_mpl(fig, caption=f"Trained on 5y, scored on full history • States={meta.get('n_states','?')} • train_window={meta.get('train_window_years','?')}y")


if __name__ == "__main__":
    main()
