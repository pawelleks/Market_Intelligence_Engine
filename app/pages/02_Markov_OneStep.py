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
from app.ui.components import SectionHeader, DataStatus, SummaryBox
from app.ui.components import read_parquet_safe, read_csv_safe, read_json_safe, fmt_percent_one_decimal

import importlib as _importlib
_derive_effective_params = _importlib.import_module("app.pages.01_Markov_Chain")._derive_effective_params

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def main():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("One-Step Next-State Probabilities")

    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    ctrl_order = st.sidebar.slider("Order", 1, 4, 1)
    ctrl_state_mode = st.sidebar.selectbox("State mode", ["binary", "tri"], index=0)
    ctrl_thr = st.sidebar.number_input("Threshold (bps)", min_value=0, max_value=1000, value=10, step=5)
    window = st.sidebar.selectbox("Window", ["MAX","1Y","2Y","5Y","10Y","20Y"], index=0)

    base = DATA / "analytics" / "markov" / ticker
    sweep = read_csv_safe(base / "order_sweep.csv")
    meta = read_json_safe(base / "metadata.json")
    available_orders = {k for k in range(1, 5) if (base / f"matrix_order{k}.parquet").exists()}
    eff_order, eff_state_mode, eff_thr = _derive_effective_params(meta, {"order": ctrl_order, "state_mode": ctrl_state_mode, "threshold_bps": ctrl_thr}, available_orders)

    if sweep is None or sweep.empty:
        DataStatus(f"offline data not found: {base / 'order_sweep.csv'}", "warning")
        return

    last = sweep[sweep["order"] == eff_order]
    if last is None or last.empty:
        DataStatus("not available offline for this order/state-mode", "warning")
        return

    row = last.iloc[-1]
    cols = [c for c in ["mc_prob_up_next", "mc_prob_neutral_next", "mc_prob_down_next"] if c in last.columns]
    if not cols:
        DataStatus("offline data present, but no *_next columns in order_sweep.csv", "warning")
        return
    names = ["Green (bullish)", "Neutral", "Red (bearish)"][: len(cols)]
    vals = [fmt_percent_one_decimal(row[c]) for c in cols]
    st.dataframe(pd.DataFrame([vals], columns=names))
    # Summary
    idx = int(row[cols].values.argmax())
    st.caption(f"Given context {row.get('latest_context','?')}, tomorrow is most likely {names[idx]} ({vals[idx]}). Params: state_mode={eff_state_mode}, thr={eff_thr}bps, order={eff_order}")

    # Fallback: try windowed matrix for active order/mode/threshold if legacy matrix missing
    mat_legacy = read_parquet_safe(base / f"matrix_order{eff_order}.parquet")
    if mat_legacy is None or mat_legacy.empty:
        mdir = base / "matrices" / eff_state_mode / f"thr{eff_thr}" / f"order{eff_order}"
        wkey = str(window).upper()
        mat_win = read_parquet_safe(mdir / f"{wkey}.parquet")
        if mat_win is None or mat_win.empty:
            DataStatus(
                f"offline data not found for order={eff_order}, state_mode={eff_state_mode}, thr={eff_thr}, window={wkey}. Build via: python cli/mie.py derive-markov-matrix --ticker {ticker} --state-mode {eff_state_mode} --threshold-bps {eff_thr} --order {eff_order} --window {wkey}",
                "warning",
            )
        else:
            st.caption(f"Loaded windowed matrix: {mdir / (wkey + '.parquet')}")


if __name__ == "__main__":
    main()
