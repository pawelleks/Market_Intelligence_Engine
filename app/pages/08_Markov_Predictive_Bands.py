# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

from pathlib import Path
import math
import numpy as np
import pandas as pd
import streamlit as st
import datetime as dt
import yaml
import matplotlib.pyplot as plt

from app.ui.theme import css_inject, get_tokens, mpl_style
from app.ui.components import DataStatus, plot_mpl

# ========= Constants =========
DATA = Path("data")
ALLOWED_WINDOWS = ("1Y","2Y","5Y","10Y","20Y","MAX")
DEFAULT_PCTS = [50, 75, 90, 95]

# ========= Small pure helpers (exported for tests) =========

def _normalize_window(window_val) -> str:
    if window_val is None:
        return "5Y"
    if isinstance(window_val, (int, float)):
        v = int(window_val)
        if v in (1,2,5,10,20):
            return f"{v}Y"
    s = str(window_val).strip().upper()
    if s in ALLOWED_WINDOWS:
        return s
    if s in {"1","2","5","10","20"}:
        return f"{s}Y"
    return "5Y"


def _window_date_bounds(feat_df: pd.DataFrame, win: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    s = pd.to_datetime(feat_df["date"]).dt.tz_localize(None)
    end = s.max().normalize()
    if win == "MAX":
        start = s.min().normalize()
    else:
        years = int(win.replace("Y",""))
        start = (end - pd.DateOffset(years=years)).normalize()
        # clamp to available
        start = max(start, s.min().normalize())
    return start, end


def _load_features_df(ticker: str) -> pd.DataFrame | None:
    p = DATA / "features" / f"{ticker}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
    # normalize close
    if "close" not in df.columns:
        for c in ("adj_close","Adj Close"):
            if c in df.columns:
                df = df.rename(columns={c: "close"})
                break
    if "ret_1d" not in df.columns and "r" in df.columns:
        df = df.rename(columns={"r":"ret_1d"})
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def _load_states_for(ticker: str, thr_bps: int, mode: str) -> pd.DataFrame | None:
    # Prefer using analytics helper if available
    try:
        from mie_lib.analytics.markov.states_model import states_for
        return states_for(ticker, int(thr_bps), str(mode))
    except Exception:
        p = DATA/"analytics"/"markov"/ticker/f"states_thr{int(thr_bps)}_{str(mode).lower()}.parquet"
        if not p.exists():
            return None
        return pd.read_parquet(p)


def _matrix_path(ticker: str, mode: str, thr: int, order: int, window: str) -> Path:
    return DATA/"analytics"/"markov"/ticker/"matrices"/str(mode).lower()/f"thr{int(thr)}"/f"order{int(order)}"/f"{_normalize_window(window)}.parquet"


def _load_markov_matrix(ticker: str, mode: str, thr: int, order: int, window: str) -> pd.DataFrame | None:
    p = _matrix_path(ticker, mode, thr, order, window)
    if not p.exists():
        return None
    return pd.read_parquet(p)


def _last_k_context(states_df: pd.DataFrame, k: int, start: pd.Timestamp, end: pd.Timestamp) -> tuple[str|None, str|None]:
    """Return (raw_udn, display_gnr). mc_state_today expected in {U,N,D}."""
    if states_df is None or states_df.empty or "mc_state_today" not in states_df.columns:
        return None, None
    s = states_df.copy()
    s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None)
    s = s[(s["date"]>=start)&(s["date"]<=end)].sort_values("date")
    if s.empty:
        s = states_df.copy(); s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None); s = s.sort_values("date")
    raw_seq = [str(x).upper() for x in s["mc_state_today"].tolist() if str(x).strip()]
    raw_seq = [x for x in raw_seq if x in {"U","N","D"}]
    if not raw_seq:
        return None, None
    raw_ctx = "".join(raw_seq[-k:])
    mp = {"U":"G","N":"N","D":"R"}
    disp = "".join(mp[c] for c in raw_ctx)
    return raw_ctx, disp


def _lookup_context_row(df: pd.DataFrame, raw_udn: str) -> pd.Series | None:
    if df is None or df.empty or not isinstance(raw_udn, str) or not raw_udn:
        return None
    # direct via 'context' column first
    if "context" in df.columns:
        m = df[df["context"].astype(str) == raw_udn]
        if not m.empty:
            return m.iloc[0]
    # then try index labels (verbose or raw)
    try:
        if raw_udn in df.index:
            sel = df.loc[raw_udn]
            return sel.iloc[0] if isinstance(sel, pd.DataFrame) else sel
    except Exception:
        pass
    return None


def _select_context_row_with_fallback(df: pd.DataFrame, raw_udn: str) -> tuple[pd.Series|None, int]:
    if df is None or df.empty or not raw_udn:
        return None, 0
    k = len(raw_udn)
    for kk in range(k, 0, -1):
        sub = raw_udn[-kk:]
        row = _lookup_context_row(df, sub)
        if isinstance(row, pd.Series):
            return row, kk
    return None, 0


def _aggregate_to_state_matrix(matrix_df: pd.DataFrame, mode: str) -> tuple[np.ndarray, list[str]]:
    """
    Aggregate context-level rows to state-level transition matrix M (2x2 or 3x3).
    Row key: current state = last char of raw context ('U','N','D').
    Columns taken from mc_prob_up/(mc_prob_neutral)/mc_prob_down.
    Weighted by 'counts' column if present, else equal weights.
    Returns (M, state_order_raw) where state_order_raw = ['U','D'] or ['U','N','D'].
    """
    if matrix_df is None or matrix_df.empty:
        return np.zeros((0,0)), []
    cols = [c for c in ["mc_prob_up","mc_prob_neutral","mc_prob_down"] if c in matrix_df.columns]
    if not cols:
        return np.zeros((0,0)), []
    is_binary = (str(mode).lower()=="binary") or ("mc_prob_neutral" not in cols)
    state_order = ["U","D"] if is_binary else ["U","N","D"]
    rows = {s: [] for s in state_order}
    wts = {s: [] for s in state_order}
    df = matrix_df.copy()
    # ensure we have a raw context string
    if "context" not in df.columns:
        df["context"] = df.index.astype(str)
    for _, r in df.iterrows():
        ctx = str(r.get("context",""))
        if not ctx:
            continue
        curr = ctx[-1]
        if curr not in rows:
            continue
        rows[curr].append([float(r.get(c, np.nan)) for c in (["mc_prob_up"] + ([] if is_binary else ["mc_prob_neutral"]) + ["mc_prob_down"])])
        wts[curr].append(float(r.get("counts", 1.0)))
    # weighted average per row
    M = []
    for s in state_order:
        arr = np.array(rows[s], dtype=float)
        if arr.size == 0:
            M.append([np.nan]*(2 if is_binary else 3))
            continue
        wt = np.array(wts[s], dtype=float)
        wt = wt / (wt.sum() if wt.sum() else 1.0)
        v = (arr * wt[:,None]).sum(axis=0)
        # normalize
        ssum = v.sum()
        if ssum and not math.isnan(ssum) and ssum != 0:
            v = v / ssum
        M.append(v.tolist())
    M = np.array(M, dtype=float)
    # sanitize rows
    row_sums = M.sum(axis=1, keepdims=True)
    row_sums[row_sums==0] = 1.0
    M = M / row_sums
    return M, state_order


def _propagate_state_probs(M: np.ndarray, p0: np.ndarray, horizons: list[int]) -> dict[int, np.ndarray]:
    out: dict[int,np.ndarray] = {}
    if M.size == 0 or p0.size == 0:
        return out
    for h in sorted(set(int(x) for x in horizons if int(x) > 0)):
        if h == 1:
            out[h] = p0.copy()
        else:
            Ph = np.linalg.matrix_power(M, h-1)
            out[h] = p0 @ Ph
    return out


def _state_moments_from_df(df_join: pd.DataFrame, mode: str, return_type: str) -> dict[str, tuple[float,float]]:
    """Return dict raw_state -> (mu, sigma) in chosen return_type space.
    If return_type == 'log', compute on lr = ln(1+ret_1d). For binary states: only 'U','D'.
    """
    if df_join is None or df_join.empty:
        return {}
    s = df_join.copy()
    s = s.dropna(subset=["ret_1d","mc_state_today"])  # mc_state_today raw U/N/D
    if return_type == "log":
        s["r_base"] = np.log1p(s["ret_1d"].astype(float))
    else:
        s["r_base"] = s["ret_1d"].astype(float)
    groups = s.groupby("mc_state_today")
    out = {}
    for k, g in groups:
        k = str(k)
        if str(mode).lower()=="binary" and k == "N":
            continue
        mu = float(np.nanmean(g["r_base"].values)) if len(g) else float("nan")
        sd = float(np.nanstd(g["r_base"].values, ddof=1)) if len(g) > 1 else float("nan")
        out[k] = (mu, sd)
    return out


def _z_for_percentile(p: int | float) -> float:
    # Common two-tailed style percentiles mapped to one-sided z from median
    mapping = {50: 0.0, 75: 0.674, 90: 1.282, 95: 1.645}
    try:
        return float(mapping.get(int(p), 0.0))
    except Exception:
        return 0.0


def _build_bands_from_probs(C0: float, probs: dict[int,np.ndarray], mu_map: dict[str,tuple[float,float]], state_order: list[str], return_type: str, percentiles: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Given per-horizon state probabilities (dict h -> vector over state_order), and per-state (mu,sigma),
    compute expected cumulative path and price percentiles.
    Returns (horizon_table, price_table) where:
      - horizon_table: index h, columns: p_up, p_neutral (if tri), p_down, E_step, CumE, price_pXX
      - price_table: index h, columns: expected, pXX
    """
    is_binary = ("N" not in state_order)
    # Build mapping from state index to (mu, sigma)
    mus = [mu_map.get(s, (0.0, 0.0))[0] for s in state_order]
    sigs = [mu_map.get(s, (0.0, 0.0))[1] for s in state_order]
    percentiles = sorted(set(int(x) for x in percentiles))
    # Accumulators
    rows = []
    price_rows = []
    cum_mean_simple = 0.0
    cum_var_simple = 0.0
    cum_mean_log = 0.0
    cum_var_log = 0.0
    for h in sorted(probs.keys()):
        ph = probs[h]
        # step expectation/variance in chosen space
        if return_type == "log":
            # weighted mean/var in log space
            m_step = float(np.dot(ph, mus))
            v_step = float(np.dot(ph, [(sigs[i]**2) + (mus[i]-m_step)**2 for i in range(len(state_order))]))
            cum_mean_log += m_step
            cum_var_log += v_step
            expected_price = C0 * math.exp(cum_mean_log)
            # build percentiles in log domain around median
            price_cols = {}
            for p in percentiles:
                z = _z_for_percentile(p)
                price_cols[f"P{p}"] = C0 * math.exp(cum_mean_log + z * math.sqrt(max(cum_var_log, 0.0)))
            # Derive simple-space step expectation for table readability
            E_step_simple = math.exp(m_step) - 1.0
            cum_simple = math.exp(cum_mean_log) - 1.0
        else:
            m_step = float(np.dot(ph, mus))
            v_step = float(np.dot(ph, [(sigs[i]**2) + (mus[i]-m_step)**2 for i in range(len(state_order))]))
            cum_mean_simple += m_step
            cum_var_simple += v_step
            expected_price = C0 * (1.0 + cum_mean_simple)
            price_cols = {}
            for p in percentiles:
                z = _z_for_percentile(p)
                price_cols[f"P{p}"] = C0 * (1.0 + cum_mean_simple + z * math.sqrt(max(cum_var_simple, 0.0)))
            E_step_simple = m_step
            cum_simple = cum_mean_simple
        # probability reporting
        idx_up = 0
        idx_neu = (None if is_binary else 1)
        idx_down = (1 if is_binary else 2)
        p_up = float(ph[idx_up])
        p_neu = (float(ph[idx_neu]) if idx_neu is not None else None)
        p_dn = float(ph[idx_down])
        row = {
            "h": h,
            "p_up": p_up,
            **({"p_neutral": p_neu} if p_neu is not None else {}),
            "p_down": p_dn,
            "E_step": E_step_simple,
            "CumE": cum_simple,
        }
        row.update({k: float(v) for k, v in price_cols.items()})
        rows.append(row)
        price_row = {"h": h, "Expected": expected_price}
        price_row.update({k: float(v) for k, v in price_cols.items()})
        price_rows.append(price_row)
    tab = pd.DataFrame(rows).set_index("h")
    price_tab = pd.DataFrame(price_rows).set_index("h")
    return tab, price_tab

# ========= UI =========

def _load_tickers_from_config() -> list[str]:
    try:
        p = Path("config/tickers.yml")
        if not p.exists():
            return ["SPY","QQQ","DIA","IWM"]
        data = yaml.safe_load(p.read_text())
        if isinstance(data, list):
            return [str(t).upper() for t in data if isinstance(t, str)]
        if isinstance(data, dict):
            out = []
            for v in data.values():
                if isinstance(v, list):
                    out.extend([str(t).upper() for t in v if isinstance(t, str)])
            return sorted(set(out)) or ["SPY","QQQ","DIA","IWM"]
    except Exception:
        pass
    return ["SPY","QQQ","DIA","IWM"]


def main():
    tokens = get_tokens()
    css_inject(tokens)
    st.title("Markov Predictive Bands")

    # Sidebar controls
    tickers = _load_tickers_from_config()
    tkr = st.sidebar.selectbox("Ticker", options=tickers, index=0)
    mode = st.sidebar.selectbox("State mode", options=["binary","tri"], index=1)
    thr = st.sidebar.number_input("Threshold (bps)", min_value=0, max_value=1000, step=5, value=10)
    order = int(st.sidebar.slider("Order (K)", 1, 4, 1))
    window = _normalize_window(st.sidebar.selectbox("Matrix window", ALLOWED_WINDOWS, index=2))
    H = int(st.sidebar.slider("Forecast horizon (days)", 1, 60, 20))
    pcts = st.sidebar.multiselect("Percentile bands", options=DEFAULT_PCTS, default=DEFAULT_PCTS)
    rtype = st.sidebar.selectbox("Return type (calc)", options=["log","simple"], index=0)
    show_hist = st.sidebar.checkbox("Show last 60 days actual", value=False)
    if st.sidebar.button("Recompute bands"):
        st.experimental_rerun()

    # Load offline artifacts
    feat = _load_features_df(tkr)
    if feat is None or feat.empty or "ret_1d" not in feat.columns:
        DataStatus(f"No features for {tkr}. Run: python cli/mie.py build-features --mode full", "warning")
        return
    mat = _load_markov_matrix(tkr, mode, int(thr), order, window)
    if mat is None or mat.empty:
        DataStatus(
            f"No Markov matrix for {tkr} (mode={mode}, thr={int(thr)}bps, K={order}, window={window}).\n"
            f"Generate via: python cli/mie.py ensure-markov-available --ticker {tkr} --state-mode {mode} --threshold-bps {int(thr)} --order {order} --window {window}",
            "warning",
        )
        return
    states = _load_states_for(tkr, int(thr), mode)

    # Resolve window bounds and current context
    w_start, w_end = _window_date_bounds(feat, window)
    raw_ctx, disp_ctx = _last_k_context(states, order, w_start, w_end)
    if raw_ctx is None:
        DataStatus("Unable to resolve current context from states; using single-state fallback.", "warning")
        # Fallback: infer last state from features via threshold if possible (approx)
        raw_ctx = "U"  # neutral fallback: Up
        disp_ctx = "G"
    row, used_k = _select_context_row_with_fallback(mat, raw_ctx)
    if not isinstance(row, pd.Series):
        DataStatus("No matrix row for the current context at this order; falling back disabled.", "warning")
        return
    if used_k < order:
        st.caption(f"Using fallback context length K={used_k} (requested {order}).")

    # Aggregate to state-level matrix and build p0
    M, state_order = _aggregate_to_state_matrix(mat, mode)
    if M.size == 0:
        DataStatus("Unable to aggregate matrix to state level.", "warning")
        return
    # p0 from selected row (next-day distribution)
    prob_cols = [c for c in ["mc_prob_up","mc_prob_neutral","mc_prob_down"] if c in mat.columns]
    if str(mode).lower()=="binary" and "mc_prob_neutral" in prob_cols:
        prob_cols = ["mc_prob_up","mc_prob_down"]
    p0 = np.array([float(row.get(c, 0.0)) for c in prob_cols], dtype=float)
    ssum = p0.sum(); p0 = p0/(ssum if ssum else 1.0)

    # Join features with states for μ,σ per state within window
    join_df = None
    if states is not None and not states.empty:
        s = states.copy(); s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None)
        j = feat.merge(s[["date","mc_state_today"]], on="date", how="inner")
        j = j[(j["date"]>=w_start)&(j["date"]<=w_end)]
        join_df = j
    moments = _state_moments_from_df(join_df, mode, rtype)

    # Section 1: Current Context & Inputs
    st.subheader("Current Context & Inputs")
    try:
        C0 = float(feat.loc[feat["date"]<=w_end, "close"].iloc[-1])
    except Exception:
        C0 = float("nan")
    st.caption(f"Last close (C0): {C0:.2f} • Previous context (display): {disp_ctx or ''} • Window: {window}")
    if moments:
        # Build μ,σ table in display labels
        def disp_label(raw):
            return {"U":"Green","N":"Neutral","D":"Red"}.get(raw, raw)
        rows = []
        for raw, (mu, sd) in moments.items():
            rows.append({"State": disp_label(raw), "μ": mu, "σ": sd})
        df_mom = pd.DataFrame(rows).set_index("State")
        st.dataframe(df_mom)
    else:
        st.info("Insufficient joined history to estimate per-state moments (μ, σ). Proceeding with zeros.")
        # zero moments map for present states
        moments = {s:(0.0,0.0) for s in state_order}

    # Propagate state probabilities 1..H
    probs = _propagate_state_probs(M, p0, list(range(1, H+1)))

    # Build bands
    tab, price_tab = _build_bands_from_probs(C0, probs, moments, state_order, rtype, pcts)

    # Section 2: Predictive Bands chart
    st.subheader(f"Markov Predictive Bands (Forward {H} Days)")
    st.caption("Bands derived from Markov state probabilities and state-conditional returns (μ, σ) using normal approximation of aggregated uncertainty.")
    try:
        fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
        mpl_style(fig, ax, tokens)
        x = price_tab.index.values
        ax.plot(x, price_tab["Expected"], label="Expected", color=tokens["theme"]["colors"].get("text"))
        # Shaded bands (ordered by percentile width)
        for p in sorted(pcts):
            key = f"P{p}"
            if key in price_tab.columns:
                ax.fill_between(x, price_tab[key], price_tab["Expected"], alpha=0.18, label=key)
        if show_hist:
            try:
                recent = feat[feat["date"] >= (w_end - pd.Timedelta(days=60))]
                ax2 = ax.twinx()
                ax2.plot(range(-len(recent)+1,1), recent["close"].values, color=tokens["theme"]["colors"].get("neutral"), alpha=0.5)
                ax2.set_yticks([])
            except Exception:
                pass
        ax.set_xlabel("Horizon (days)"); ax.set_ylabel("Price")
        leg = ax.legend(loc="upper left", fontsize=8, frameon=True)
        try:
            leg.get_frame().set_alpha(0.3)
        except Exception:
            pass
        fig.tight_layout()
        plot_mpl(fig)
    except Exception:
        st.caption("Chart unavailable.")

    # Section 3: Horizon Probability & Expectation Table
    st.subheader("Horizon Probability & Expectation Table")
    if not tab.empty:
        disp = tab.copy()
        # Probabilities to percents
        for col in [c for c in disp.columns if c.startswith("p_")]:
            disp[col] = disp[col].map(lambda x: f"{(float(x)*100.0):.2f}%")
        # Returns as simple %
        disp["E_step"] = disp["E_step"].map(lambda x: f"{(float(x)*100.0):.2f}%")
        disp["CumE"] = disp["CumE"].map(lambda x: f"{(float(x)*100.0):.2f}%")
        # Prices with 2 decimals
        for c in [c for c in tab.columns if c.startswith("P")]:
            disp[c] = tab[c].map(lambda x: f"{float(x):.2f}")
        st.dataframe(disp)
    else:
        st.caption("No horizon table.")

    # Section 4: Coverage Backtest (optional, H=1)
    st.subheader("Coverage Backtest (last 250 days, optional)")
    if st.checkbox("Run 1-day coverage backtest", value=False):
        try:
            n = 250
            s_end = w_end
            s_start = s_end - pd.Timedelta(days=n*2)  # allow non-trading days
            f = feat[(feat["date"]>=s_start)&(feat["date"]<=s_end)].copy()
            f = f.reset_index(drop=True)
            if len(f) > 2:
                hits = {p:0 for p in pcts}
                total = 0
                # Use constant p0 and M as approximation (UI-only)
                for i in range(1, len(f)):
                    total += 1
                    # expected and bands for 1 step
                    one_probs = {1: probs[1]}
                    _, pt = _build_bands_from_probs(float(f.loc[i-1,"close"]), one_probs, moments, state_order, rtype, pcts)
                    realized = float(f.loc[i, "close"])
                    for p in pcts:
                        key = f"P{p}"
                        if key in pt.columns:
                            lo = min(float(pt.loc[1, key]), float(pt.loc[1, "Expected"]))
                            hi = max(float(pt.loc[1, key]), float(pt.loc[1, "Expected"]))
                            if lo <= realized <= hi:
                                hits[p] += 1
                if total > 0:
                    res = pd.DataFrame({"percentile": [f"P{p}" for p in pcts], "coverage": [hits[p]/total for p in pcts]})
                    try:
                        import altair as alt
                        ch = alt.Chart(res).mark_bar().encode(x="percentile", y=alt.Y("coverage", axis=alt.Axis(format=".0%")))
                        st.altair_chart(ch, use_container_width=True)
                    except Exception:
                        st.bar_chart(res.set_index("percentile")["coverage"])
            else:
                st.caption("Insufficient history for backtest.")
        except Exception:
            st.caption("Backtest failed (non-fatal).")


if __name__ == "__main__":
    main()
