# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

import streamlit as st
import pandas as pd
from pathlib import Path
import os
import datetime as dt

from app.ui.theme import get_tokens, css_inject
from app.version import get_version

# ----------------------------
# Pure helpers (import-safe)
# ----------------------------
RAW_DIR = Path(ROOT) / "data" / "raw"

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

    # Load data
    df_raw, path_used = _safe_read_raw(use_ticker)
    if df_raw is None or path_used is None:
        st.warning(f"No offline data found for {use_ticker}.")
        return
    df_norm = _normalize_price_df(df_raw)
    if df_norm.empty:
        st.warning(f"Raw data for {use_ticker} missing required OHLC columns.")
        return

    # Compute daily returns (ascending), then take most recent N rows (descending for display)
    df_returns = _compute_daily_returns(df_norm)
    df_disp = df_returns.sort_values("date", ascending=False).head(rows_choice).copy()

    # Format columns
    df_disp["Date"] = df_disp["date"].dt.strftime("%Y-%m-%d")
    # Keep Daily Change numeric here; style will format with {:+.2f}%
    df_disp["Daily Change (%)"] = df_disp["daily_return_pct"].astype(float)
    display_cols = ["Date","open","high","low","close","Daily Change (%)"]
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
    st.caption(f"Ticker: {use_ticker} • Rows: {rows_choice} • Source: offline • Data range: {coverage_min} – {coverage_max}")

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
    except Exception:
        st.dataframe(df_display_final, use_container_width=True)

    # Summary sentence
    recent_slice = df_disp
    up_days = int((recent_slice["daily_return_pct"] > 0).sum())
    down_days = int((recent_slice["daily_return_pct"] < 0).sum())
    latest_change = recent_slice.iloc[0]["daily_return_pct"] if not recent_slice.empty else float('nan')
    latest_str = _format_pct(latest_change)
    # Color inline using basic span (avoid heavy styling) within markdown
    c = tokens.get("theme", {}).get("colors", {})
    green = c.get("bull") or c.get("green")
    red = c.get("bear") or c.get("red")
    # No inline hex; if no tokens, render plain text without span
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

    try:
        st.divider()
    except Exception:
        st.markdown("---")

# Run when executed directly by Streamlit
if __name__ == "__main__":
    main()
