from mie_lib.utils.paths import DATA_DIR

import streamlit as st
import pandas as pd
from pathlib import Path
import datetime as dt

from app.ui.theme import get_tokens, css_inject
from app.version import get_version
from core.state_classification import classify_tri_state

# NEW: shared error + preflight utilities
try:
    from app.ui.errors import render_exception, render_missing_artifact, render_empty_state
except Exception:
    def render_exception(section_title: str, exc: Exception, hint: str | None = None):
        st.error(section_title)
        st.caption(f"{exc.__class__.__name__}: {exc}")
        if hint:
            st.info(hint)
    def render_missing_artifact(section_title: str, path: Path | str, fix_hint: str):
        st.warning(section_title)
        st.caption(f"Expected: {path}")
        st.write(fix_hint)
    def render_empty_state(section_title: str, message: str):
        st.info(section_title)
        st.caption(message)

try:
    from mie_lib.utils.preflight import find_latest_feature, ensure_parquet, simple_cli_hint
except Exception:
    def find_latest_feature(ticker: str):
        p = Path("data/features") / f"{ticker}.parquet"; return p if p.exists() else None
    def ensure_parquet(path: Path, required_cols: list[str]):
        try:
            df = pd.read_parquet(path); return df, [c for c in required_cols if c not in df.columns], ""
        except Exception as e:
            return None, required_cols, str(e)
    def simple_cli_hint(kind: str, ticker: str):
        return "Run: python cli/mie.py build-features --mode full" if kind=="features" else "See cli/mie.py"

# ----------------------------
# Pure helpers (import-safe)
# ----------------------------
RAW_DIR = DATA_DIR / "raw"

_DISPLAY_TICKERS = ["SPY", "QQQ", "DIA", "IWM"]

def _safe_read_raw(ticker: str) -> tuple[pd.DataFrame | None, Path | None]:
    """Load raw daily price data for ticker from parquet (preferred) else csv.
    Returns (df, path) or (None, None) if not found. Read-only.
    """
    t = ticker.upper().strip()
    pq = RAW_DIR / f"{t}.parquet"
    if pq.exists():
        try:
            return pd.read_parquet(pq), pq
        except Exception:
            pass
    csv = RAW_DIR / f"{t}.csv"
    if csv.exists():
        try:
            return pd.read_csv(csv), csv
        except Exception:
            pass
    return None, None

def _normalize_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure required columns & types; add 'close' from 'adj_close' if close missing.
    Returns a copy sorted ascending by date.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # flexible date column handling
    date_col = None
    for cand in ["date", "Date", "DATE"]:
        if cand in out.columns:
            date_col = cand
            break
    if date_col is None:
        # attempt to find index date
        out = out.reset_index()
        for cand in ["date", "index"]:
            if cand in out.columns:
                date_col = cand
                break
    if date_col is None:
        return pd.DataFrame()
    out.rename(columns={date_col: "date"}, inplace=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    # unify column names
    rename_map = {c: c.lower() for c in out.columns}
    out.rename(columns=rename_map, inplace=True)
    if "close" not in out.columns and "adj_close" in out.columns:
        out["close"] = out["adj_close"]
    needed = ["open", "high", "low", "close"]
    # keep only necessary + date
    keep = [c for c in ["date"] + needed if c in out.columns]
    out = out[keep].dropna(subset=["date"]).sort_values("date")
    return out.reset_index(drop=True)

def _compute_daily_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Add daily_return_pct column (float) based on prior close.
    First row -> NaN. Assumes df is sorted ascending by date.
    Pure computation; no styling.
    """
    if df is None or df.empty or "close" not in df.columns:
        return pd.DataFrame(columns=["date","open","high","low","close","daily_return_pct"])  # empty schema
    out = df.copy()
    prev_close = out["close"].shift(1)
    out["daily_return_pct"] = (out["close"] / prev_close - 1.0) * 100.0
    return out

def _format_pct(val: float) -> str:
    if pd.isna(val):
        return ""  # blank for first row
    return f"{val:+.2f}%"  # include sign

def _style_table(df: pd.DataFrame, tokens: dict):
    """Return a Styler with colored daily change column using theme colors.
    Green for >0, Red for <0, Neutral for ==0 or blank. Uses theme tokens only; if
    tokens are unavailable, returns default styling without inline colors.
    """
    colors = tokens.get("theme", {}).get("colors", {}) if isinstance(tokens, dict) else {}
    green = colors.get("bull") or colors.get("green")
    red = colors.get("bear") or colors.get("red")
    neutral = colors.get("neutral") or colors.get("blue") or colors.get("fg")

    def color_daily(val: str):
        # Without token colors, skip coloring entirely
        if not (green or red or neutral):
            return ""
        if not val:
            return f"color: {neutral}" if neutral else ""
        try:
            num = float(val.replace("%", ""))
        except Exception:
            return f"color: {neutral}" if neutral else ""
        if num > 0 and green:
            return f"color: {green}; font-weight:600"
        if num < 0 and red:
            return f"color: {red}; font-weight:600"
        return f"color: {neutral}" if neutral else ""

    sty = df.style.format(
        {
            "open": "{:.2f}", "high": "{:.2f}", "low": "{:.2f}", "close": "{:.2f}", "Daily Change (%)": lambda v: v,
        },
        na_rep="",
    )
    sty = sty.set_properties(subset=["open","high","low","close"], **{"text-align":"right"})
    sty = sty.set_properties(subset=["Daily Change (%)"], **{"text-align":"right"})
    sty = sty.apply(lambda col: [color_daily(v) for v in col] if col.name == "Daily Change (%)" else ["" for _ in col], axis=0)
    return sty

# ----------------------------
# Page main
# ----------------------------

def main():
    tokens = get_tokens(); css_inject(tokens)
    st.title("Price & Daily Returns Viewer")

    # Controls
    st.sidebar.header("Filters")
    selected_ticker = st.sidebar.selectbox("Ticker", _DISPLAY_TICKERS, index=0)
    custom_ticker = st.sidebar.text_input("Custom ticker (optional)", "")
    use_ticker = custom_ticker.strip().upper() if custom_ticker.strip() else selected_ticker
    rows_choice = st.sidebar.selectbox("Rows to display", [50, 100, 200], index=0)
    state_mode = st.sidebar.selectbox("State mode", ["tri", "binary"], index=0)
    threshold_bps = st.sidebar.slider("Threshold (bps)", min_value=0, max_value=150, value=10, step=5)

    # Preflight feature artifact
    try:
        feat_path = find_latest_feature(use_ticker)
        if feat_path is None:
            render_missing_artifact("Features", Path("data/features")/f"{use_ticker}.parquet", simple_cli_hint("features", use_ticker))
            return
        _df_check, missing_cols, err = ensure_parquet(feat_path, ["date"])
        if _df_check is None:
            render_exception("Features load error", RuntimeError(err), hint=simple_cli_hint("features", use_ticker))
            return
    except Exception as e:
        render_exception("Features preflight failed", e, hint=simple_cli_hint("features", use_ticker))
        return

    # Load data (raw ingestion fallback still allowed)
    df_raw, path_used = _safe_read_raw(use_ticker)
    if df_raw is None or path_used is None:
        render_missing_artifact("Raw price data", RAW_DIR / f"{use_ticker}.parquet", simple_cli_hint("features", use_ticker))
        return
    df_norm = _normalize_price_df(df_raw)
    if df_norm.empty:
        render_empty_state("Normalized price data", f"Raw data for {use_ticker} missing required OHLC columns.")
        return

    # Compute daily returns (ascending), then take most recent N rows (descending for display)
    df_returns = _compute_daily_returns(df_norm)
    if df_returns.empty:
        render_empty_state("Daily returns", "Unable to compute daily returns (missing close price).")
        return
    df_disp = df_returns.sort_values("date", ascending=False).head(rows_choice).copy()

    # Classification
    try:
        if state_mode == "tri":
            df_disp["State"] = [classify_tri_state(r/100.0 if not pd.isna(r) else float('nan'), threshold_bps) if not pd.isna(r) else "" for r in df_disp["daily_return_pct"].values]
        elif state_mode == "binary":
            tmp_states = [classify_tri_state(r/100.0 if not pd.isna(r) else float('nan'), threshold_bps) if not pd.isna(r) else "" for r in df_disp["daily_return_pct"].values]
            df_disp["State"] = ["Green" if s == "Green" else ("Red" if s in {"Red","Neutral"} else "") for s in tmp_states]
        else:
            df_disp["State"] = "N/A"
    except Exception as e:
        render_exception("State classification", e)
        df_disp["State"] = ""

    df_disp["Date"] = df_disp["date"].dt.strftime("%Y-%m-%d")
    df_disp["Daily Change (%)"] = df_disp["daily_return_pct"].astype(float)
    display_cols = ["Date","open","high","low","close","Daily Change (%)","State"]
    df_display_final = df_disp[display_cols].rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"})

    # Meta line
    try:
        mtime = path_used.stat().st_mtime
        last_updated = dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime > 0 else "n/a"
    except Exception:
        last_updated = "n/a"
    coverage_min = df_norm["date"].min().strftime("%Y-%m-%d") if not df_norm.empty else "?"
    coverage_max = df_norm["date"].max().strftime("%Y-%m-%d") if not df_norm.empty else "?"
    st.caption(f"Version: {get_version()} • Last updated: {last_updated} • Data coverage for {use_ticker}: {coverage_min} – {coverage_max}")

    # Section
    st.subheader("Recent OHLC & Daily Performance")
    st.caption(f"Ticker: {use_ticker} • Rows: {rows_choice} • Source: offline • Data range: {coverage_min} – {coverage_max} • State mode: {state_mode} • Threshold: {threshold_bps}bps")

    # Styled table
    try:
        colors = tokens.get("theme", {}).get("colors", {}) if isinstance(tokens, dict) else {}
        green = colors.get("bull") or colors.get("green")
        red = colors.get("bear") or colors.get("red")
        def _color_sign(val):
            try:
                if pd.isna(val) or float(val) == 0.0:
                    return ""
                if float(val) > 0 and green:
                    return f"color: {green}; font-weight:600"
                if float(val) < 0 and red:
                    return f"color: {red}; font-weight:600"
                return ""
            except Exception:
                return ""
        sty = (
            df_display_final.style
            .format({"Open":"{:.2f}", "High":"{:.2f}", "Low":"{:.2f}", "Close":"{:.2f}", "Daily Change (%)": "{:+.2f}%"}, na_rep="")
            .set_properties(subset=["Open","High","Low","Close"], **{"text-align":"right"})
            .set_properties(subset=["Daily Change (%)"], **{"text-align":"right"})
            .applymap(_color_sign, subset=["Daily Change (%)"])  # color only this column
        )
        st.dataframe(sty, use_container_width=True)
    except Exception as e:
        render_exception("Styled table", e)
        st.dataframe(df_display_final, use_container_width=True)

    # Summary sentence
    try:
        recent_slice = df_disp
        up_days = int((recent_slice["daily_return_pct"] > 0).sum())
        down_days = int((recent_slice["daily_return_pct"] < 0).sum())
        latest_change = recent_slice.iloc[0]["daily_return_pct"] if not recent_slice.empty else float('nan')
        latest_str = _format_pct(latest_change)
        c = tokens.get("theme", {}).get("colors", {})
        green = c.get("bull") or c.get("green")
        red = c.get("bear") or c.get("red")
        if latest_str.startswith("+") and green:
            latest_html = f"<span style='color:{green};font-weight:600'>{latest_str}</span>"
        elif latest_str.startswith("-") and red:
            latest_html = f"<span style='color:{red};font-weight:600'>{latest_str}</span>"
        else:
            latest_html = latest_str or 'n/a'
        st.markdown(
            f"Over the last {rows_choice} sessions, {use_ticker} had {up_days} up days and {down_days} down days; latest session change: {latest_html}.",
            unsafe_allow_html=True,
        )
    except Exception as e:
        render_exception("Summary", e)

    try:
        st.divider()
    except Exception:
        st.markdown("---")

# Run when executed directly by Streamlit
if __name__ == "__main__":
    main()
