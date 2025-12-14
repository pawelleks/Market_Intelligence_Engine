# --- path shim (must be first) ---
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np  # add after other imports
from app.ui.theme import get_tokens, css_inject, mpl_style
from app.utils import _render_section_header, _display_table, _format_metric, _get_ticker_colors

# --------------------------------------------------------------------------------------------------
# Page Config & Theme
# --------------------------------------------------------------------------------------------------
st.set_page_config(page_title="Seasonality Sample", layout="wide")
css_inject()
TOKENS = get_tokens()
COLORS = _get_ticker_colors()

# --------------------------------------------------------------------------------------------------
# Data Loading (stub / offline friendly)
# --------------------------------------------------------------------------------------------------
SEASONALITY_BASE_DIR = _ROOT / "data" / "seasonality" / "base"

def _load_seasonality_base(ticker: str) -> pd.DataFrame:
    """Attempt to load precomputed seasonality base parquet, fallback to synthetic sample.
    Expected columns: ticker, date, year, doy_trading, open, high, low, close, r, lr
    """
    path = SEASONALITY_BASE_DIR / f"{ticker}.parquet"
    if path.exists():
        try:
            df = pd.read_parquet(path)
            # enforce ordering & dtypes minimally
            df = df.sort_values("date").reset_index(drop=True)
            return df
        except Exception:  # pragma: no cover - defensive
            pass
    # Fallback synthetic (3 years * first 5 trading days)
    dates = pd.date_range("2023-01-03", periods=15, freq="B")
    years = [d.year for d in dates]
    day_of_year = [d.timetuple().tm_yday for d in dates]
    df = pd.DataFrame({
        "ticker": ticker,
        "date": dates,
        "year": years,
        "doy_trading": ((pd.Series(day_of_year) % 5) + 1).astype(int),
        "open": [100 + i for i in range(len(dates))],
        "high": [100.5 + i for i in range(len(dates))],
        "low":  [99.5 + i for i in range(len(dates))],
        "close": [100.2 + i for i in range(len(dates))],
    })
    df["r"] = df["close"].pct_change()
    df["lr"] = np.log(df["close"] / df["close"].shift(1)).fillna(0.0)
    return df

# --------------------------------------------------------------------------------------------------
# Early Seasonality Table (stub logic)
# --------------------------------------------------------------------------------------------------

def _build_early_seasonality_table(df: pd.DataFrame, lookback_days: int = 10) -> pd.DataFrame:
    recent = df.tail(lookback_days).copy()
    # Format metrics using helper
    recent["Return %"] = recent["r"].apply(lambda v: _format_metric(v * 100, "%") if pd.notna(v) else "")
    recent["Log r (bp)"] = recent["lr"].apply(lambda v: _format_metric(v * 10000, "bp") if pd.notna(v) else "")
    display_cols = ["date", "doy_trading", "close", "Return %", "Log r (bp)"]
    return recent[display_cols]

# --------------------------------------------------------------------------------------------------
# Chart Helper
# --------------------------------------------------------------------------------------------------

def _render_price_trace(df: pd.DataFrame, ticker: str):
    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=140)
    # Choose color from ticker mapping, then fall back to theme tokens (no inline hex)
    theme_colors = TOKENS.get("theme", {}).get("colors", {})
    color = (
        COLORS.get(ticker)
        or theme_colors.get("accent_blue")
        or theme_colors.get("primary")
        or theme_colors.get("bull")
        or theme_colors.get("fg")
    )
    ax.plot(df["date"], df["close"], label=f"{ticker} Close", color=color)
    ax.set_xlabel("Date")
    ax.set_ylabel("Close")
    ax.legend(loc="upper left", fontsize=8)
    mpl_style(fig, ax, TOKENS)
    st.pyplot(fig, width="stretch")

# --------------------------------------------------------------------------------------------------
# Page Rendering
# --------------------------------------------------------------------------------------------------

def main():
    ticker = st.sidebar.selectbox("Ticker", ["SPY", "QQQ", "DIA", "IWM"], index=0)
    lookback = st.sidebar.selectbox("Rows", [10, 20, 50], index=0)

    df = _load_seasonality_base(ticker)
    if df.empty:
        st.info(f"No seasonality data available for {ticker}.")
        return

    _render_section_header("Early Seasonality Table")
    tbl = _build_early_seasonality_table(df, lookback)
    _display_table(tbl, caption=f"Most recent {len(tbl)} sessions • {ticker}")

    _render_section_header("SPY Price Trace (Sample)")
    _render_price_trace(df.tail(lookback * 3), ticker)

if __name__ == "__main__":  # pragma: no cover
    main()
