"""
Streamlit page: Markov Chain Analysis (V2)

Architecture-compliant, modular, and using only precomputed data.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# --- Page Setup ---
st.set_page_config(page_title="Markov Chain V2", layout="wide")

# --- Project-specific Imports (library only) ---
from mie_lib.analytics.markov.aggregation import aggregate_to_state_matrix
from mie_lib.analytics.markov.helpers import compute_multi_horizon_probs
from mie_lib.analytics.markov.state_codes import to_compact, to_verbose
from mie_lib.analytics.markov import states_for
from mie_lib.utils.paths import DATA_DIR, markov_matrix_grid_path
# Use canonical V1-compatible context selection helper
from mie_lib.pages.m_chain import _select_active_context_row

# --- Color & Label Helpers ---
_DISPLAY_WORD = {"G": "Green", "N": "Neutral", "R": "Red"}
_COLOR_MAP = {"G": "green", "N": "blue", "R": "red"}

def _colored_word(code: str) -> str:
    """Formats a state code (G/N/R) into a colored word."""
    word = _DISPLAY_WORD.get(code, code)
    color = _COLOR_MAP.get(code, "white")
    return f":{color}[{word}]"

def _context_words(context: str) -> str:
    """Formats a compact context string (e.g., "GRN") into colored words."""
    if not context:
        return ""
    return " → ".join(_colored_word(c) for c in context)

# --- Compatibility Shim for Tests ---
def _compute_horizon_probs(matrix_df, context_label, horizons, mode="binary"):
    """Shim for legacy tests."""
    return compute_multi_horizon_probs(matrix_df, context_label, horizons, mode=mode)

# --- Data Loaders ---
@st.cache_data(show_spinner=False)
def _load_features(ticker: str) -> pd.DataFrame | None:
    """Loads the features file for a given ticker."""
    path = DATA_DIR / "features" / f"{ticker}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)

@st.cache_data(show_spinner=False)
def _load_states(ticker: str, mode: str, threshold: int) -> pd.DataFrame | None:
    """Loads states using library API and adapts to expected schema (adds 'raw_state')."""
    try:
        df = states_for(ticker, int(threshold), str(mode))
    except Exception:
        return None
    if df is None or df.empty:
        return None
    out = df.copy()
    if "raw_state" not in out.columns and "mc_state_today" in out.columns:
        out["raw_state"] = out["mc_state_today"].astype(str)
    return out

@st.cache_data(show_spinner=False)
def _load_matrix(ticker: str, window: str, mode: str, threshold: int, order: int) -> pd.DataFrame | None:
    """Loads the transition matrix for a given configuration."""
    path = markov_matrix_grid_path(ticker, mode, threshold, order, window)
    if not path.exists():
        return None
    return pd.read_parquet(path)

def _get_cli_hint(ticker, mode, thr, order, window) -> str:
    """Generates the CLI hint for ensuring artifacts exist using actual CLI signature.
    NOTE: Keep in sync with cli/mie.py -> build_parser() subparser 'ensure-markov-available'.
    Required flags (no positionals):
      --ticker TICKER --state-mode {tri,binary} --threshold-bps INT --order INT --window {1Y,2Y,5Y,10Y,20Y,MAX}
    """
    return (
        f"python cli/mie.py ensure-markov-available "
        f"--ticker {ticker} --state-mode {mode} --threshold-bps {thr} "
        f"--order {order} --window {window}"
    )

# --- Main Page Rendering ---
def main():
    """Renders the Markov Chain V2 page."""
    # --- Sidebar Inputs ---
    with st.sidebar:
        st.header("Markov Chain V2")
        # TODO: Load tickers from a config file
        tickers = ["SPY", "QQQ", "DIA", "IWM", "^GSPC", "^NDX", "^DJI", "^RUT"]
        ticker = st.selectbox("Ticker", tickers, index=0)
        window_key = st.select_slider(
            "Window",
            options=["1Y", "2Y", "5Y", "10Y", "20Y", "MAX"],
            value="5Y"
        )
        state_mode = st.radio("State Mode", ["binary", "tri"], index=1, horizontal=True)
        threshold_bps = st.slider("Threshold (bps)", 0, 150, 10, 5)
        order = st.slider("Order (K)", 1, 4, 1)
        horizons = st.multiselect("Horizons (days)", [1, 2, 3, 4, 5, 10, 20, 60], default=[1, 2, 3, 4])
        # Add cache clear for post-CLI rebuilds
        if st.button("🔄 Clear data cache & reload"):
            st.cache_data.clear()
            st.rerun()

    # --- Data Loading & Preflight Checks ---
    feat_df = _load_features(ticker)
    mat_df = _load_matrix(ticker, window_key, state_mode, threshold_bps, order)
    states_df = _load_states(ticker, state_mode, threshold_bps)

    # --- Lag Detection ---
    if feat_df is not None and not feat_df.empty:
        last_feat_date = pd.to_datetime(feat_df["date"].max()).date()
        today = datetime.now(timezone.utc).date()
        lag_days = (today - last_feat_date).days
        if lag_days > 1:
            st.caption(f"⚠️ Analytics data lags spot by {lag_days} days (features last updated: {last_feat_date}).")

    # --- Diagnostics Expander ---
    with st.expander("Diagnostics"):
        st.json({
            "ticker": ticker,
            "window": window_key,
            "state_mode": state_mode,
            "threshold_bps": threshold_bps,
            "order": order,
            "matrix_path": str(markov_matrix_grid_path(ticker, state_mode, threshold_bps, order, window_key)),
            "matrix_exists": mat_df is not None,
            "matrix_rows": (len(mat_df) if mat_df is not None else 0),
            "states_source": "states_for() API",
            "states_exists": states_df is not None,
            "states_rows": (len(states_df) if states_df is not None else 0),
            "features_exist": feat_df is not None,
            "features_rows": (len(feat_df) if feat_df is not None else 0),
        })

    # --- Main Content ---
    if mat_df is None or mat_df.empty:
        st.warning("Markov matrix not found for this configuration.")
        st.code(_get_cli_hint(ticker, state_mode, threshold_bps, order, window_key))
        st.caption("After running the command above, press ‘Clear data cache & reload’ in the sidebar.")
        st.stop()

    if states_df is None or states_df.empty:
        st.warning("Markov states not found for this configuration.")
        st.code(
            f"python cli/mie.py build-markov-states --ticker {ticker} --state-modes {state_mode} --thresholds {threshold_bps}"
        )
        st.stop()

    # --- Active Context Selection (reuse canonical helper from V1) ---
    # Compute date range from features (fallback to unknown strings if unavailable)
    if feat_df is not None and not feat_df.empty and "date" in feat_df.columns:
        _start_iso = pd.to_datetime(feat_df["date"]).min().date().isoformat()
        _end_iso = pd.to_datetime(feat_df["date"]).max().date().isoformat()
    else:
        _start_iso, _end_iso = ("unknown", "unknown")
    # Select active context row using the same logic as V1
    _ctx_raw, _ctx_disp_compact, ctx_row, _used_k = _select_active_context_row(
        mat_df=mat_df,
        states_df=states_df,
        mode=state_mode,
        order=int(order),
        start_date=_start_iso,
        end_date=_end_iso,
    )
    used_context_compact = _ctx_disp_compact

    if ctx_row is None:
        st.info("Context row not found for the latest state sequence. Rebuild the grid for this configuration.")
        st.code(_get_cli_hint(ticker, state_mode, threshold_bps, order, window_key))
        st.caption("After running the command above, press ‘Clear data cache & reload’ in the sidebar.")
        st.stop()

    # --- 1. Transition Matrix Section ---
    st.subheader("Transition Matrix")
    st.dataframe(mat_df, use_container_width=True)

    # Unified Summary Sentence
    summary_intro, summary_main, summary_cont = "", "", ""
    prob_cols = [c for c in ctx_row.index if c.startswith("mc_prob_")]
    if prob_cols:
        next_probs = ctx_row[prob_cols]
        best_next_col = next_probs.idxmax()
        best_next_code = {"mc_prob_up": "G", "mc_prob_neutral": "N", "mc_prob_down": "R"}.get(best_next_col, "?")
        best_prob_val = next_probs.max()

        last_state_code = used_context_compact[-1]
        last_state_col_name = {"G": "mc_prob_up", "N": "mc_prob_neutral", "R": "mc_prob_down"}.get(last_state_code)
        continuation_prob = ctx_row.get(last_state_col_name, 0.0)

        summary_intro = f"Given previous context was {_context_words(used_context_compact)},"
        summary_main = f"the next state is most likely {_colored_word(best_next_code)} ({best_prob_val:.1%})."
        summary_cont = f"Continuation (stay last-state {_colored_word(last_state_code)}) = {continuation_prob:.1%}."

        st.markdown(f"**Conclusion:** {summary_intro} {summary_main} {summary_cont}")

    # --- 2. Transition Probability Heatmap ---
    st.subheader("Transition Probability Heatmap")
    try:
        import plotly.express as px
        heatmap_df = mat_df.set_index('context')[prob_cols]
        heatmap_df.columns = [c.replace('mc_prob_', '').capitalize() for c in heatmap_df.columns]
        fig = px.imshow(heatmap_df, text_auto=".1%", aspect="auto",
                        labels=dict(x="Next State", y="Previous Context", color="Probability"),
                        color_continuous_scale="RdYlGn")
        fig.update_layout(title_text="Transition Probabilities", title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Active context row for summaries: **{used_context_compact}**")
    except ImportError:
        st.info("Plotly not installed. Skipping heatmap.")
    except Exception as e:
        st.error(f"Could not render heatmap: {e}")


    # --- 3. One-Step Next-State Summary ---
    st.subheader("One-Step Next-State Summary")
    one_step_df = pd.DataFrame(ctx_row[prob_cols]).T
    one_step_df.columns = [c.replace('mc_prob_', '').capitalize() for c in one_step_df.columns]
    one_step_df.index = [_context_words(used_context_compact)]
    st.dataframe(one_step_df.style.format("{:.2%}"))
    st.markdown(f"**Conclusion:** {summary_intro} {summary_main} {summary_cont}")


    # --- 4. Multi-Horizon Probability Table + Mini Chart ---
    st.subheader("Multi-Horizon Probability Table")
    try:
        agg_matrix = aggregate_to_state_matrix(mat_df, state_mode)
        horizon_df = compute_multi_horizon_probs(agg_matrix, used_context_compact, horizons, mode=state_mode)

        if horizon_df is not None and not horizon_df.empty:
            st.dataframe(horizon_df.style.format("{:.2%}"))

            # Mini Chart
            st.bar_chart(horizon_df)

            # Summary Line
            avg_probs = horizon_df.mean()
            top_state = avg_probs.idxmax()
            bias_summary = ", ".join(f"{_colored_word(k)} ≈ {v:.1%}" for k, v in avg_probs.items())
            change_summary = ""
            if top_state in horizon_df.columns:
                min_p, max_p = horizon_df[top_state].min(), horizon_df[top_state].max()
                change_summary = f"{_colored_word(top_state)} probability changes {min_p:.1%} → {max_p:.1%} over {horizons[-1]} days."

            st.markdown(f"**Start context:** {_context_words(used_context_compact)}. **Overall bias:** {bias_summary}. {change_summary}")

    except Exception as e:
        st.error(f"Failed to compute multi-horizon probabilities: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"An unexpected error occurred on the page: {e.__class__.__name__}: {e}")
        with st.expander("Show Traceback"):
            import traceback
            st.code(traceback.format_exc())
