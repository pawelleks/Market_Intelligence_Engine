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
import importlib as _importlib

from app.ui.theme import css_inject, get_tokens
from app.ui.components import SectionHeader, DataStatus
from app.ui.components import read_parquet_safe, read_csv_safe, read_json_safe, fmt_percent_one_decimal

_derive_effective_params = _importlib.import_module("app.pages.01_Markov_Chain")._derive_effective_params

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Multi-Step Forecast (1st-Order Approximation)")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    base = DATA / "analytics" / "markov" / ticker
    ctrl_order = st.sidebar.slider("Order", 1, 4, 1)
    ctrl_state_mode = st.sidebar.selectbox("State mode", ["binary", "tri"], index=0)
    ctrl_thr = st.sidebar.number_input("Threshold (bps)", min_value=0, max_value=1000, value=10, step=5)
    window = st.sidebar.selectbox("Window", ["MAX","1Y","2Y","5Y","10Y","20Y"], index=0)
    meta = read_json_safe(base / "metadata.json")
    available_orders = {k for k in range(1, 5) if (base / f"matrix_order{k}.parquet").exists()}
    eff_order, eff_state_mode, eff_thr = _derive_effective_params(meta, {"order": ctrl_order, "state_mode": ctrl_state_mode, "threshold_bps": ctrl_thr}, available_orders)

    pred = read_parquet_safe(base / "predictions.parquet")
    if pred is None or pred.empty:
        # Fallback: if predictions not present, at least ensure windowed matrix exists to allow display-only multi-step later
        mdir = base / "matrices" / ctrl_state_mode / f"thr{ctrl_thr}" / f"order{ctrl_order}"
        wkey = str(window).upper()
        mat_win = read_parquet_safe(mdir / f"{wkey}.parquet")
        if mat_win is None or mat_win.empty:
            DataStatus(f"offline data not found: {base / 'predictions.parquet'} and windowed matrix missing. Build via: python cli/mie.py derive-markov-matrix --ticker {ticker} --state-mode {ctrl_state_mode} --threshold-bps {ctrl_thr} --order {ctrl_order} --window {wkey}", "warning")
            return
        else:
            st.caption(f"Loaded windowed matrix for display-only multi-step: {mdir / (wkey + '.parquet')}")
            # Minimal display-only: show first row probabilities as placeholder
            st.dataframe(mat_win.head(1))
            return

    # pick last 4 horizons if columns available
    cols = [c for c in pred.columns if c.startswith("horizon_")]
    if not cols:
        DataStatus("offline data present, but no horizon_* columns", "warning")
        return

    st.dataframe(pred[cols].tail(1))
    st.caption(f"Placeholder: chart to show side-by-side bars by horizon with Green/Neutral/Red shares. Params: state_mode={eff_state_mode}, thr={eff_thr}bps, order={eff_order}")


if __name__ == "__main__":
    main()
