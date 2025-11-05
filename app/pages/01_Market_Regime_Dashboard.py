# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]  # parent of "app"
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import os
from pathlib import Path
import math
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import json

from app.ui.theme import get_tokens, css_inject, mpl_style, fmt_pct
from app.ui.theme import get_metric_labels, color_for_status
from app.ui.components import SectionHeader, Card, SummaryBox, ExpandableChart, DataStatus, DownloadRow
from app.ui.components import plot_mpl, apply_friendly_labels, fmt_percent_two_decimals

# Use stable repo-relative DATA path
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


@st.cache_data(ttl=600)
def _read_parquet(path: Path):
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


@st.cache_data(ttl=600)
def _read_csv(path: Path):
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


@st.cache_data(ttl=600)
def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _freshness_text(paths):
    times = []
    for p in paths:
        if p and Path(p).exists():
            times.append(Path(p).stat().st_mtime)
    if not times:
        return ""
    latest = max(times)
    from datetime import datetime
    return f"Data freshness: {datetime.fromtimestamp(latest).isoformat(sep=' ', timespec='minutes')}"


# ===== HMM chart helpers =====

def load_price_and_hmm(ticker: str):
    """Load features price, hmm states, and optional probs; merge by date.
    Returns (merged_df, probs_df_or_none)
    merged_df columns: date, price, hmm_state_name
    If probs present, columns hmm_prob_bull/hmm_prob_bear/(neutral) are merged as well.
    """
    feat_p = DATA_DIR / "features" / f"{ticker}.parquet"
    hmm_dir = DATA_DIR / "analytics" / "hmm" / ticker
    states_p = hmm_dir / "hmm_states.parquet"
    probs_p = hmm_dir / "hmm_probs.parquet"

    df_feat = _read_parquet(feat_p)
    df_states = _read_parquet(states_p)
    if df_feat is None or df_states is None:
        return None, None

    # normalize date
    for df in (df_feat, df_states):
        if "date" not in df.columns:
            df.reset_index(inplace=True)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    # price column: prefer adj_close (case-insensitive), fallback close
    cols = {c.lower(): c for c in df_feat.columns}
    price_col = cols.get("adj_close") or cols.get("adj close") or cols.get("close")
    if price_col is None:
        return None, None
    price = df_feat[["date", price_col]].rename(columns={price_col: "price"})

    merged = price.merge(df_states[["date", "hmm_state_name"]], on="date", how="left").sort_values("date")
    df_probs = _read_parquet(probs_p)
    if df_probs is not None and "date" in df_probs.columns:
        df_probs["date"] = pd.to_datetime(df_probs["date"]).dt.tz_localize(None)
        # keep known prob cols if present
        prob_cols = [c for c in df_probs.columns if c.startswith("hmm_prob_")]
        merged = merged.merge(df_probs[["date"] + prob_cols], on="date", how="left")
    else:
        df_probs = None

    return merged.reset_index(drop=True), df_probs


def _downsample(df: pd.DataFrame, max_points: int) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = math.ceil(len(df) / max_points)
    return df.iloc[::step, :].reset_index(drop=True)


def draw_hmm_regimes_chart(df: pd.DataFrame, tokens: dict, width: int, height: int):
    """Return a Matplotlib fig for price with regime bands.
    df must contain columns: date, price, hmm_state_name (and optional probs)
    """
    colors = tokens["theme"]["colors"]
    max_pts = int(tokens["theme"]["chart"]["max_points"])
    dfd = df.copy()
    dfd = dfd.sort_values("date").reset_index(drop=True)
    dfd = _downsample(dfd, max_pts)

    fig, ax = plt.subplots(figsize=(max(4, width / 100), max(2, height / 100)), dpi=100)
    mpl_style(fig, ax, tokens)

    # price line
    ax.plot(dfd["date"], dfd["price"], color=color_for_status("neutral"), linewidth=1.2, label="Price")

    # Regime bands via axvspan for contiguous stretches
    def state_color(name: str) -> str:
        if str(name) == "Bull":
            return color_for_status("bull")
        if str(name) == "Bear":
            return color_for_status("bear")
        return color_for_status("neutral")

    # identify runs of same state
    last_state = None
    run_start = None
    dates = dfd["date"].tolist()
    states = dfd["hmm_state_name"].fillna("Neutral").tolist()
    for i, (dt, stname) in enumerate(zip(dates, states)):
        if last_state is None:
            last_state = stname
            run_start = dt
        elif stname != last_state:
            # end previous span at previous date
            ax.axvspan(run_start, dates[i - 1], color=state_color(last_state), alpha=0.08)
            last_state = stname
            run_start = dt
    # close last run
    if last_state is not None and run_start is not None and len(dates) > 0:
        ax.axvspan(run_start, dates[-1], color=state_color(last_state), alpha=0.08)

    ax.set_xlabel("")
    ax.set_ylabel("Price", color=colors["text"])
    ax.legend(loc="upper left", fontsize=tokens["theme"]["font"]["size_small"])

    fig.tight_layout()
    return fig


def _summary_text(df_probs: pd.DataFrame | None, df_states: pd.DataFrame) -> str:
    # recent regime from states
    recent_state = str(df_states["hmm_state_name"].dropna().iloc[-1]) if "hmm_state_name" in df_states.columns and len(df_states.dropna(subset=["hmm_state_name"])) else "Unknown"
    if df_probs is not None and not df_probs.empty:
        tail = df_probs.tail(20)
        bull = tail.get("hmm_prob_bull")
        bear = tail.get("hmm_prob_bear")
        neutral = tail.get("hmm_prob_neutral")
        bull_avg = fmt_pct(bull.mean()) if bull is not None else "NA%"
        bear_avg = fmt_pct(bear.mean()) if bear is not None else "NA%"
        if neutral is not None:
            neutral_avg = fmt_pct(neutral.mean())
            return f"Recent regime: {recent_state}. Over the last 20 trading days, avg Bull={bull_avg}, Neutral={neutral_avg}, Bear={bear_avg}."
        else:
            return f"Recent regime: {recent_state}. Over the last 20 trading days, avg Bull={bull_avg} vs Bear={bear_avg}."
    return f"Recent regime: {recent_state}. Probabilities unavailable; summary will include them once probs are produced."


def render():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Market Regime Dashboard")

    # Controls
    ticker = st.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    history = st.selectbox("History", ["1Y", "3Y", "5Y", "Max"], index=2)

    hmm_dir = DATA_DIR / "analytics" / "hmm" / ticker
    mk_dir = DATA_DIR / "analytics" / "markov" / ticker

    # Section A: SPY Price with HMM Regimes
    SectionHeader("SPY Price with HMM Regimes", f"Ticker={ticker}, Window={history}")

    def body_hmm():
        # Robust loads: states, probs, metadata (independent of UI history)
        meta = _read_json(hmm_dir / "hmm_metadata.json")
        df_states = _read_parquet(hmm_dir / "hmm_states.parquet")
        df_probs = _read_parquet(hmm_dir / "hmm_probs.parquet")
        if df_states is None or df_states.empty:
            # Show single info with CLI
            years_map = {"1Y": 1, "3Y": 3, "5Y": 5, "Max": 5}
            years = years_map.get(history, 5)
            st.info(f"HMM not found. Build via: python cli/mie.py build-hmm --ticker {ticker} --states 2 --window-years {years}")
            return
        # If available, note training window vs UI
        if meta and isinstance(meta, dict) and "train_window_years" in meta:
            years_map = {"1Y": 1, "3Y": 3, "5Y": 5, "Max": meta.get("train_window_years", 5)}
            if years_map.get(history) != meta.get("train_window_years"):
                st.caption(
                    f"HMM built on {meta.get('train_window_years')}y; page showing {history}. Rebuild for exact match if needed."
                )
        # Merge for chart
        merged = None
        if df_probs is not None:
            merged = df_states.merge(df_probs, on="date", how="left")
        else:
            merged = df_states.copy()
        # Render chart + summary
        w = int(tokens["theme"]["chart"]["default_width"])
        h = int(tokens["theme"]["chart"]["default_height"])

        def _render(tokens_local):
            # Build price series from features for the same ticker
            feat_p = DATA_DIR / "features" / f"{ticker}.parquet"
            feats = _read_parquet(feat_p)
            if feats is None or feats.empty:
                DataStatus("Features not found for price overlay", "warn")
                return
            # Normalize price
            cols = {c.lower(): c for c in feats.columns}
            price_col = cols.get("adj_close") or cols.get("adj close") or cols.get("close")
            if price_col is None:
                DataStatus("Price columns missing in features", "warn")
                return
            price = feats[["date", price_col]].rename(columns={price_col: "price"})
            dfm = price.merge(df_states[["date", "hmm_state_name"]], on="date", how="left")
            if dfm.empty or "price" not in dfm.columns or "hmm_state_name" not in dfm.columns:
                DataStatus("HMM outputs present, but no data to plot", "warn")
                return
            fig = draw_hmm_regimes_chart(dfm, tokens_local, width=w, height=h)
            plot_mpl(fig)

        ExpandableChart(_render, tokens)
        SummaryBox(_summary_text(df_probs, df_states))

    Card("HMM Regimes", f"Files: hmm_states.parquet, hmm_probs.parquet", body_hmm)

    # Section B: Markov Order Sweep — Latest Context
    SectionHeader("Markov Order Sweep — Latest Context", None)

    def body_sweep():
        labels = get_metric_labels()
        df_sweep = _read_csv(mk_dir / "order_sweep.csv")
        if df_sweep is None or df_sweep.empty:
            DataStatus("Markov order_sweep.csv not found. Build via: python cli/mie.py build-markov-sweep --ticker {ticker} --orders 1,2,3,4 --state-mode tri --threshold-bps 10", "info")
            return
        # Bar chart with friendly labels
        prob_cols = [c for c in df_sweep.columns if c.startswith("mc_prob_")]
        friendly = {c: labels.get(c, c) for c in prob_cols}
        tiny = df_sweep.set_index("order")[prob_cols].rename(columns=friendly)
        st.bar_chart(tiny.rename(columns={
            "Probability: Up next": "Up",
            "Probability: Neutral next": "Neutral",
            "Probability: Down next": "Down",
        }))
        # Summary line for latest context from the highest order present
        last = df_sweep.sort_values("order").iloc[-1]
        ctx = last.get("latest_context", "?")
        parts = []
        if "mc_prob_up_next" in df_sweep.columns:
            parts.append(f"{labels['mc_prob_up_next']}={fmt_pct(last['mc_prob_up_next']/1.0 if pd.notna(last['mc_prob_up_next']) else 0)}")
        if "mc_prob_neutral_next" in df_sweep.columns and pd.notna(last.get("mc_prob_neutral_next")):
            parts.append(f"{labels['mc_prob_neutral_next']}={fmt_pct(last['mc_prob_neutral_next']/1.0)}")
        if "mc_prob_down_next" in df_sweep.columns:
            parts.append(f"{labels['mc_prob_down_next']}={fmt_pct(last['mc_prob_down_next']/1.0 if pd.notna(last['mc_prob_down_next']) else 0)}")
        support = int(last.get("support_count", 0))
        cov = float(last.get("coverage_pct", 0))
        st.markdown(
            f"<div class='small'>Latest context: <span class='accent'>{ctx}</span>. Probability — Up next={fmt_pct(last.get('mc_prob_up_next', 0),1)}, Neutral next={fmt_pct(last.get('mc_prob_neutral_next', 0),1)}, Down next={fmt_pct(last.get('mc_prob_down_next', 0),1)} (support={support}, coverage={fmt_pct(cov,1)}).</div>",
            unsafe_allow_html=True,
        )

    Card("Order Sweep", "Latest context probability snapshot", body_sweep)

    # Section C: One-step Next-State Table
    SectionHeader("One-step Next-State Table", None)

    def body_one_step():
        labels = get_metric_labels()
        p = mk_dir / "matrix_order1.parquet"
        df = _read_parquet(p)
        if df is None or df.empty:
            DataStatus(
                f"matrix_order1.parquet not found. Build via: python cli/mie.py build-markov --ticker {ticker} --order 1 --state-mode tri --threshold-bps 10",
                "info",
            )
            return
        # Determine available columns (tri vs binary)
        cols = [c for c in ["mc_prob_up", "mc_prob_neutral", "mc_prob_down"] if c in df.columns]
        if not cols:
            DataStatus("No probability columns in matrix_order1.parquet", "warn")
            return
        # Build compact table for canonical contexts if present
        contexts = ["U", "N", "D"] if "mc_prob_neutral" in cols else ["U", "D"]
        sub = df[df["context"].isin(contexts)][["context"] + cols].copy()
        sub = sub.drop_duplicates("context").set_index("context").reindex(contexts)
        sub = sub.rename(columns={c: labels.get(c, c) for c in cols})
        # Format percent with 2 decimals for probability columns
        fmt = {labels.get("mc_prob_up", "mc_prob_up"): fmt_percent_two_decimals}
        if "mc_prob_neutral" in cols:
            fmt[labels.get("mc_prob_neutral", "mc_prob_neutral")] = fmt_percent_two_decimals
        fmt[labels.get("mc_prob_down", "mc_prob_down")] = fmt_percent_two_decimals
        st.dataframe(sub, column_config={k: st.column_config.TextColumn() for k in sub.columns}, hide_index=False)
        SummaryBox("One-step next-state probabilities shown for canonical contexts.")

    Card("One-step Markov Matrix", "K=1", body_one_step)

    # Freshness line
    st.markdown(
        f"<div class='muted'>{_freshness_text([hmm_dir / 'hmm_states.parquet', hmm_dir / 'hmm_probs.parquet', mk_dir / 'order_sweep.csv', mk_dir / 'matrix_order1.parquet'])}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    render()
