from mie_lib.utils.paths import DATA_DIR

import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from datetime import datetime

# Set page configuration early (before any other Streamlit UI calls)
st.set_page_config(page_title="Seasonality Analysis", layout="wide")

# NEW: shared error + preflight utilities
try:
    from app.ui.errors import render_exception, render_missing_artifact, render_empty_state
except Exception:  # safe fallbacks
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
    from mie_lib.utils.preflight import ensure_parquet, find_seasonality_base, simple_cli_hint
except Exception:
    def ensure_parquet(path: Path, required_cols: list[str]):
        try:
            df = pd.read_parquet(path)
            return df, [c for c in required_cols if c not in df.columns], ""
        except Exception as e:
            return None, required_cols, str(e)
    def find_seasonality_base(ticker: str) -> Path | None:
        p = Path("data/seasonality/base") / f"{ticker}.parquet"
        return p if p.exists() else None
    def simple_cli_hint(kind: str, ticker: str) -> str:
        return f"Run: python cli/mie.py build-seasonality-base --ticker \"{ticker}\"" if kind=="seasonality" else "See cli/mie.py"

# Try to import UL System helpers; provide safe fallbacks if unavailable
try:
    from app.utils import (
        _render_section_header as _ul_render_section_header,  # alias original
        _display_table,
        _format_metric,
        _get_ticker_colors,
    )
except Exception:  # Safe minimal fallbacks
    _ul_render_section_header = None

    def _display_table(df: pd.DataFrame, **kwargs):
        import streamlit as st
        st.dataframe(df, use_container_width=True)

    def _format_metric(x, kind: str = "%") -> str:
        try:
            if kind == "%":
                return f"{x:.1%}"
            if kind == "bp":
                return f"{x:.0f} bp"
            if kind == "z":
                return f"{x:.2f}"
        except Exception:
            return ""
        return str(x)

    def _get_ticker_colors(ticker: str) -> dict:
        return {"primary": "primary", "accent": "accent", "warn": "warn"}

# Always provide a local UL-compliant wrapper that supports optional subtitle (overrides imported one if any)
def _render_section_header(title: str, subtitle: str | None = None) -> None:
    """Standard UL System section header for Seasonality pages.
    Accepts an optional subtitle; uses subheader + caption per UI_README_v2 and CHART_SPECS_v2.
    This wrapper ensures backward compatibility if the original utility only accepted a single arg.
    """
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)

# ------------------------------ Constants ------------------------------
SEAS_BASE_DIR = DATA_DIR / "seasonality" / "base"
SEAS_FACTS_DIR = DATA_DIR / "analytics" / "seasonality"
CONFIG_DIR = Path("config")
SEAS_CFG = CONFIG_DIR / "seasonality.yml"
TICKERS_CFG = CONFIG_DIR / "tickers.yml"
FEATURES_DIR = DATA_DIR / "features"

# ------------------------------ Cached loaders ------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def _load_tickers() -> list[str]:
    import yaml
    if not TICKERS_CFG.exists():
        return ["SPY", "QQQ", "DIA", "IWM"]
    cfg = yaml.safe_load(TICKERS_CFG.read_text()) or {}
    tickers: list[str] = []
    for k in ("tickers", "universe", "etfs", "equities"):
        v = cfg.get(k)
        if isinstance(v, list):
            tickers.extend([str(x).strip().upper() for x in v if str(x).strip()])
        elif isinstance(v, dict):
            tickers.extend([str(x).strip().upper() for x in v.values() if str(x).strip()])
    tickers = sorted({t for t in tickers if t})
    return tickers or ["SPY", "QQQ", "DIA", "IWM"]

@st.cache_data(ttl=900, show_spinner=False)
def _list_available_seasonality_tickers() -> list[str]:
    """Intersect configured tickers with existing seasonality base files.
    Ensures support for symbols with special characters (e.g., ^GSPC) by matching exact filenames.
    """
    cfg_tickers = set(_load_tickers())
    if not SEAS_BASE_DIR.exists():
        return sorted(cfg_tickers)
    base_files = [p.name[:-8] for p in SEAS_BASE_DIR.glob("*.parquet")]  # strip .parquet
    available = sorted(cfg_tickers.intersection(set(base_files)))
    # If intersection empty (e.g., first run), fall back to full configured list
    return available or sorted(cfg_tickers)

@st.cache_data(ttl=3600, show_spinner=False)
def _load_seasonality_base(ticker: str) -> pd.DataFrame | None:
    p = SEAS_BASE_DIR / f"{ticker}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    # Normalize core columns
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True)
    # Alias tdoy -> doy_trading if needed
    if "doy_trading" not in df.columns and "tdoy" in df.columns:
        try:
            df["doy_trading"] = df["tdoy"].astype(int)
        except Exception:
            pass
    # Derive returns if missing (simple r and log lr)
    needed = {"ticker","date","year","doy_trading","open","high","low","close","r","lr"}
    if "r" not in df.columns and "close" in df.columns:
        df = df.sort_values("date").assign(r=df["close"].pct_change())
    if "lr" not in df.columns and "close" in df.columns:
        with np.errstate(divide='ignore', invalid='ignore'):
            df = df.sort_values("date").assign(lr=np.log(df["close"].pct_change().add(1.0)))
    # Month/day for calendar logic
    if "month" not in df.columns:
        df["month"] = pd.to_datetime(df["date"]).dt.month
    if "day" not in df.columns:
        df["day"] = pd.to_datetime(df["date"]).dt.day
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def _load_seasonality_config() -> dict:
    import yaml
    defaults = {"LOOKBACK_WINDOWS": [5,10,20,30,50, "ALL"], "MIN_VALID_YEARS": 5, "RETURN_TYPE": "log", "CACHE_TTL_MINUTES": 60}
    if not SEAS_CFG.exists():
        return defaults
    try:
        raw = SEAS_CFG.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            return defaults
        for k,v in defaults.items():
            data.setdefault(k, v)
        return data
    except Exception:
        st.caption("Using default seasonality settings (config parse error).")
        return defaults

# NEW: load price series used by drill-down (features-based)
@st.cache_data(ttl=900, show_spinner=False)
def _load_price_series(ticker: str) -> pd.DataFrame:
    p = FEATURES_DIR / f"{ticker}.parquet"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(p)
    except Exception:
        return pd.DataFrame()
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    price_col = None
    for c in ["close", "adj_close", "Close", "Adj Close"]:
        if c in df.columns:
            price_col = c
            break
    if price_col is None:
        return pd.DataFrame()
    df = df.sort_values("date").reset_index(drop=True)
    df["close"] = df[price_col].astype(float)
    df["prev_close"] = df["close"].shift(1)
    df["ret_pct"] = (df["close"] / df["prev_close"] - 1.0) * 100.0
    df["year"] = df["date"].dt.year
    df["tdoy"] = df.groupby("year").cumcount() + 1
    return df[["date","year","tdoy","prev_close","close","ret_pct"]]

# NEW: full-year business-day mapping to ensure curves extend to Dec
@st.cache_data(ttl=1800, show_spinner=False)
def _build_fullyear_bday_map(reference_year: int, max_doy: int | None) -> pd.DataFrame:
    """Build mapping from trading-day index (1..N) to synthetic calendar dates within a full year.
    Uses Monday–Friday business days over the reference_year. If max_doy provided, truncate mapping to that DOY.
    """
    # Generate all weekdays in the year
    start = datetime(reference_year, 1, 1)
    end = datetime(reference_year, 12, 31)
    all_days = pd.date_range(start, end, freq='C')  # CustomBusinessDay default: Mon-Fri
    # Ensure at least ~252 entries; fallback to B if needed
    if len(all_days) < 200:
        all_days = pd.date_range(start, end, freq='B')
    mapping = pd.DataFrame({
        'doy_trading': np.arange(1, len(all_days)+1, dtype=int),
        'x_date': all_days
    })
    if max_doy is not None and max_doy > 0:
        mapping = mapping[mapping['doy_trading'] <= int(max_doy)]
    return mapping

@st.cache_data(ttl=1800, show_spinner=False)
def _compute_calendar_table(df: pd.DataFrame, lookback: str, min_valid_years: int, return_type: str) -> pd.DataFrame:
    """Build day x month average same-day returns table for selected lookback.
    Values displayed as simple percent changes. Excludes current year for baseline consistency.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    latest_year = int(d["year"].max())
    hist = d[d["year"] < latest_year].copy()
    if hist.empty:
        return pd.DataFrame()
    # Subset by lookback
    if lookback != "ALL":
        try:
            n = int(lookback)
            hist = hist[hist["year"] >= latest_year - n]
        except Exception:
            pass
    # Choose base return (simple for display) always 'r' fallback
    base_ret_col = "r" if "r" in hist.columns else ("lr" if "lr" in hist.columns else None)
    if base_ret_col is None:
        return pd.DataFrame()
    # If using log returns for calculation, convert to simple daily percent for averaging
    if base_ret_col == "lr":
        hist["ret_disp"] = np.exp(hist[base_ret_col]) - 1.0
    else:
        hist["ret_disp"] = hist[base_ret_col]
    # Aggregate average by month/day
    agg = hist.groupby(["month", "day"])['ret_disp'].agg(['mean','count']).reset_index()
    agg = agg[agg['count'] >= min_valid_years]
    if agg.empty:
        return pd.DataFrame()
    agg['mean_pct'] = agg['mean']*100.0
    # Pivot to day x month
    pivot = agg.pivot(index='day', columns='month', values='mean_pct').sort_index()
    # Fill with NaN for absent entries; will style later
    return pivot

# ------------------------------ Formatting & plotting helpers ------------------------------
def _safe_pct(s: pd.Series) -> pd.Series:
    return (s * 100.0).round(2)


# Deterministic, named color mapping for horizons and current year
_DEF_COLOR_MAP = {
    "current": "red",
    "all": "cyan",        # was 'tab:cyan'
    "5y": "green",         # was 'tab:green'
    "10y": "blue",         # was 'tab:blue'
    "15y": "orange",       # was 'tab:orange'
    "20y": "purple",       # was 'tab:purple'
    "30y": "brown",        # was 'tab:brown'
    "50y": "pink",         # was 'tab:pink'
}

def _normalize_lb_key(label: str) -> str:
    s = str(label).strip().lower()
    if s in ("all", "max"):
        return "all"
    if s.endswith("y"):
        s = s[:-1]
    return f"{s}y" if s.isdigit() else s


def _get_seasonality_color(label: str) -> str:
    key = _normalize_lb_key(label)
    return _DEF_COLOR_MAP.get(key, "gray")

# --- Robust drill-down price loader helpers ---
DATA = Path("data")

# Image-based calendar heatmap rendering (high-DPI, top month labels, black text)
@st.cache_data(ttl=1800, show_spinner=False)
def _render_seasonality_calendar_image(ticker: str, lookback: str, pivot: pd.DataFrame, last_date: pd.Timestamp | None):
    """Render a matplotlib Figure for the seasonality calendar heatmap.
    Uses a diverging colormap centered at 0 (red→white→green); overlays value text and highlights today's cell.
    Returns the matplotlib Figure for downstream rendering via st.pyplot.
    """
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
    from matplotlib.patches import Rectangle

    # Prepare matrix of shape (31 days x 12 months)
    days = list(range(1, 32))
    months = list(range(1, 13))
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    M = np.full((len(days), len(months)), np.nan, dtype=float)
    for m in months:
        if m in pivot.columns:
            col = pivot[m]
            for d_idx, d in enumerate(days):
                v = col.get(d, np.nan)
                M[d_idx, m-1] = v

    # Compute symmetric normalization bounds around zero
    vlim = np.nanmax(np.abs(M))
    vlim = float(vlim) if np.isfinite(vlim) and vlim > 0 else 1.0
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)

    # Create figure with white background and high DPI for crisp text
    fig, ax = plt.subplots(figsize=(18, 10), facecolor="white")

    # Red→White→Green named colormap (no inline hex) and nearest interpolation for sharp edges
    cmap = LinearSegmentedColormap.from_list("rwg", ["red", "white", "green"])
    ax.imshow(M, cmap=cmap, norm=norm, aspect="auto", origin="upper", interpolation="nearest")

    # Move month labels to TOP and configure ticks/labels (all black)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(month_names, rotation=0, ha="center", color="black")
    ax.set_yticks(range(len(days)))
    ax.set_yticklabels([str(d) for d in days], color="black")
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.tick_params(axis="x", which="both", labelsize=10, pad=5, colors="black")
    ax.tick_params(axis="y", which="both", labelsize=9, colors="black")
    ax.tick_params(bottom=False)

    # Thin light-gray grid lines between cells using minor grid
    nrows, ncols = M.shape
    ax.set_xticks(np.arange(-0.5, ncols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, nrows, 1), minor=True)
    ax.grid(which="minor", color="lightgray", linestyle="-", linewidth=0.5)

    # Overlay black text per cell (always black for maximum readability)
    for r in range(M.shape[0]):
        for c in range(M.shape[1]):
            val = M[r, c]
            if not np.isfinite(val):
                continue
            ax.text(c, r, f"{val:+.2f}%", ha="center", va="center", color="black", fontsize=10)

    # Highlight today's calendar cell with a black rectangular border (if present in grid)
    try:
        today = pd.Timestamp.today()
        dday = int(today.day)
        mmon = int(today.month)
        if 1 <= dday <= 31 and 1 <= mmon <= 12:
            ax.add_patch(Rectangle((mmon-1-0.5, dday-1-0.5), 1.0, 1.0, fill=False, linewidth=2.5, edgecolor="black", zorder=10))
    except Exception:
        pass

    # Titles (main title as suptitle, subtitle as axes title) centered and black
    main_title = f"{ticker} • Seasonality Calendar — Same-Day Average Return (%)"
    sub_title = (
        f"Based on lookback {lookback} (excluding current year)"
        + (f"; data through {last_date.date()}" if last_date is not None and pd.notna(last_date) else "")
    )
    fig.suptitle(main_title, fontsize=14, fontweight="bold", color="black", y=0.98)
    ax.set_title(sub_title, fontsize=10, color="black", pad=20)

    # Layout and export at high DPI
    fig.tight_layout()
    return fig

def _first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None

@st.cache_data(ttl=900, show_spinner=False)
def _load_price_for_drilldown(ticker: str):
    """
    Returns (df, diags) where df has ['date','close','ret_pct'] and diags explains which source was used.
    Tries features first, then raw. Normalizes tz-naive dates and 'close' column.
    """
    diags = {"features_path": None, "raw_path": None, "used": None, "reason": None}
    # 1) Features
    fpath = DATA / "features" / f"{ticker}.parquet"
    diags["features_path"] = str(fpath)
    if fpath.exists():
        try:
            fdf = pd.read_parquet(fpath)
            fdf["date"] = pd.to_datetime(fdf["date"], utc=True).dt.tz_convert(None)
            close_col = _first_col(fdf, ["close_final", "close", "adj_close"])
            if close_col is None:
                raise KeyError("no close-like column in features")
            out = fdf[["date", close_col]].rename(columns={close_col: "close"}).dropna()
            if "ret_1d" in fdf.columns:
                out["ret_pct"] = fdf["ret_1d"] * 100.0
            else:
                out["ret_pct"] = out["close"].pct_change() * 100.0
            diags["used"] = "features"
            return out.dropna().sort_values("date").reset_index(drop=True), diags
        except Exception as e:
            diags["reason"] = f"features load error: {type(e).__name__}: {e}"
    # 2) Raw
    rpath = DATA / "raw" / f"{ticker}.parquet"
    diags["raw_path"] = str(rpath)
    if rpath.exists():
        try:
            rdf = pd.read_parquet(rpath)
            rdf["date"] = pd.to_datetime(rdf["date"], utc=True).dt.tz_convert(None)
            close_col = _first_col(rdf, ["Adj Close", "Close", "close", "adj_close"])
            if close_col is None:
                raise KeyError("no close-like column in raw")
            out = rdf[["date", close_col]].rename(columns={close_col: "close"}).dropna()
            out["ret_pct"] = out["close"].pct_change() * 100.0
            diags["used"] = "raw"
            return out.dropna().sort_values("date").reset_index(drop=True), diags
        except Exception as e:
            diags["reason"] = f"raw load error: {type(e).__name__}: {e}"
    if diags["reason"] is None:
        diags["reason"] = "no features/raw file found"
    return None, diags

# Update explainer (remove correlation reference)

def _render_page_explainer() -> None:
    """Concise textual explainer (UL System tone)."""
    st.caption(
        """**How to read this page**  \n- **Ticker**: selects the symbol's historical path.  \n- **Seasonality horizons**: past windows (excluding current year) used to build average cumulative paths.  \n- **Return type**: calculations in chosen space (log or simple); displayed as cumulative %.  \n- **Seasonality vs. Actual**: average cumulative paths vs current year's normalized path.  \n- **Calendar**: average same-day % move by calendar day for selected calendar lookback.  \n"""
    )

# ------------------------------ New drill-down helpers ------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def _get_calendar_day_sample(
    ticker: str,
    lookback_label: str,
    month: int,
    day: int,
) -> pd.DataFrame:
    """Extract full underlying sample for a (month, day) consistent with the Calendar view.
    - Excludes current year.
    - Applies year-based lookback (last N full years where applicable) identical to the calendar table.
    - Computes simple daily returns from prev_close and close.
    Returns columns: [date, year, prev_close, close, diff, ret_pct].
    """
    df = _load_seasonality_base(ticker)
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None)
    latest_year = int(d["year"].max())
    # Exclude current year
    hist = d[d["year"] < latest_year].copy()
    if lookback_label != "ALL":
        try:
            n = int(lookback_label)
            hist = hist[hist["year"] >= latest_year - n]
        except Exception:
            pass
    if hist.empty:
        return pd.DataFrame()
    # Ensure we have close; if not, stop
    price_col = "close" if "close" in hist.columns else ("adj_close" if "adj_close" in hist.columns else None)
    if price_col is None:
        return pd.DataFrame()
    hist = hist.sort_values("date")
    # Compute prev_close across the entire subset
    hist["prev_close"] = hist[price_col].shift(1)
    # Keep only selected calendar day
    hist = hist[(hist["month"] == int(month)) & (hist["day"] == int(day))]
    if hist.empty:
        return pd.DataFrame()
    # Drop rows without previous close
    hist = hist.dropna(subset=["prev_close"])
    if hist.empty:
        return pd.DataFrame()
    # Compute diff and simple return %
    hist["close_val"] = hist[price_col].astype(float)
    hist["diff"] = hist["close_val"] - hist["prev_close"].astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        hist["ret_pct"] = (hist["close_val"] / hist["prev_close"].astype(float) - 1.0) * 100.0
    out = hist[["date", "year", "prev_close", "close_val", "diff", "ret_pct"]].rename(columns={"close_val": "close"})
    out = out.sort_values("date").reset_index(drop=True)
    return out


def format_calendar_day_explanation(
    ticker: str,
    lookback_label: str,
    month: int,
    day: int,
    samples: pd.DataFrame,
) -> str:
    """Produce a concise human-readable explanation about the selected calendar day samples.
    Clarifies why observations can be less than the requested lookback.
    """
    month_name = datetime(2000, int(month), 1).strftime("%B")
    if samples is None or samples.empty:
        return (
            f"No trading history for {ticker} on {month_name} {day} under lookback {lookback_label}. "
            "This date may fall on weekends/holidays in many years."
        )
    n = len(samples)
    mean_ret = float(samples["ret_pct"].mean())
    median_ret = float(samples["ret_pct"].median())
    hit_ratio = float((samples["ret_pct"] > 0).mean()) * 100.0
    return (
        f"This calendar cell aggregates {n} occurrences for {ticker} on {month_name} {day} over a {lookback_label} window. "
        f"Mean = {mean_ret:.2f}%, median = {median_ret:.2f}%, hit ratio (>0) = {hit_ratio:.0f}%. "
        "Note: If this date falls on weekends/holidays in some years, the observation count can be smaller than the lookback window."
    )


# ------------------------------ Page render ------------------------------
# Sidebar-based controls

# Insert seasonal curve + features price loaders before main (needed by main)
@st.cache_data(show_spinner=False, ttl=600)
def _load_features_price(ticker: str) -> pd.DataFrame:
    """Load features parquet for ticker and return tidy price frame with calendar helpers.
    Columns: ['date','close','year','month','day','tdoy'].
    """
    path = Path("data") / "features" / f"{ticker}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"features parquet not found: {path}")
    df = pd.read_parquet(path)
    if "date" not in df.columns:
        raise KeyError('features parquet missing "date" column')
    d = pd.to_datetime(df["date"], utc=True, errors="coerce")
    d = d.dt.tz_convert(None) if hasattr(d, "dt") else pd.to_datetime(d)
    df = df.assign(date=d).dropna(subset=["date"]).sort_values("date")
    df = df[~df["date"].duplicated(keep="last")]
    price_col = None
    for c in ("close", "adj_close", "Close", "Adj Close"):
        if c in df.columns:
            price_col = c
            break
    if price_col is None:
        raise KeyError("no price column found (expected 'close' or 'adj_close')")
    df = df.rename(columns={price_col: "close"})[["date", "close"]].copy()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["tdoy"] = df.groupby("year").cumcount() + 1
    return df

# Removed obsolete forward stubs; real implementations defined below.

@st.cache_data(ttl=900, show_spinner=False)
def _compute_seasonal_curves(df: pd.DataFrame, lookbacks: list[str], ret_type: str):
    """Compute historical seasonal cumulative average paths and current year path.
    Returns (curves_df, current_year_df, tdoy_date_map).
    curves_df columns: ['lookback','doy_trading','cum_ret'] (decimal cumulative return).
    current_year_df columns: ['doy_trading','cum_ret'].
    tdoy_date_map columns: ['doy_trading','date']
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])  # tolerant
    latest_year = int(d["year"].max())
    # Select return column based on ret_type preference, fall back gracefully
    if str(ret_type).lower() in {"log", "lr"} and "lr" in d.columns:
        base_col = "lr"
        def _cum(series: pd.Series) -> pd.Series:
            return (series.fillna(0).cumsum()).pipe(np.exp).sub(1.0)
    else:
        base_col = "r" if "r" in d.columns else None
        if base_col is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        def _cum(series: pd.Series) -> pd.Series:
            return series.fillna(0).cumsum()

    # Historical averages by trading-day-of-year (exclude current year)
    hist = d[d["year"] < latest_year].copy()
    if hist.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Build cumulative curves for each lookback
    rows = []
    for lb in lookbacks or ["ALL"]:
        h = hist
        if str(lb).upper() != "ALL":
            try:
                n = int(lb)
                h = h[h["year"] >= latest_year - n]
            except Exception:
                pass
        if h.empty:
            continue
        # average daily return by doy_trading, then cumulative
        avg = h.groupby("doy_trading")[base_col].mean().sort_index()
        cum = _cum(avg)
        tmp = pd.DataFrame({"lookback": str(lb).upper(), "doy_trading": cum.index.astype(int), "cum_ret": cum.values})
        rows.append(tmp)
    curves_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    # Current year cumulative path (using the same return convention)
    cur = d[d["year"] == latest_year].copy().sort_values("date")
    if cur.empty:
        current_year_df = pd.DataFrame()
    else:
        current_year_df = pd.DataFrame({
            "doy_trading": cur["doy_trading"].astype(int).values,
            "cum_ret": _cum(cur[base_col]).values,
        })

    # Map trading-day to date using current year dates if present; else synthesize
    if not cur.empty and "date" in cur.columns:
        tdoy_date_map = cur[["doy_trading", "date"]].drop_duplicates("doy_trading")
    else:
        max_doy = int(d["doy_trading"].max()) if "doy_trading" in d.columns else None
        ref_year = latest_year if pd.notna(latest_year) else pd.Timestamp.today().year
        m = _build_fullyear_bday_map(int(ref_year), max_doy)
        tdoy_date_map = m.rename(columns={"x_date": "date"})
    return curves_df, current_year_df, tdoy_date_map


def main():
    # Sidebar controls
    with st.sidebar:
        tickers = _list_available_seasonality_tickers()
        sel_idx = 0 if not tickers else 0
        ticker = st.selectbox("Ticker", tickers or ["SPY"], index=sel_idx).strip().upper()
        cfg = _load_seasonality_config()
        windows = cfg.get("LOOKBACK_WINDOWS", [5, 10, 20, 30, 50, "ALL"])  # used for both curves and calendar
        default_curves = [w for w in windows if str(w).upper() in {"5", "10", "ALL"} or w in (5, 10, "ALL")]
        curves_lb = st.multiselect("Seasonality horizons (exclude current year)", [str(w).upper() for w in windows], default=[str(w).upper() for w in default_curves] or ["5","10","ALL"])
        ret_type = st.radio("Return type", ["log", "simple"], index=0 if str(cfg.get("RETURN_TYPE", "log")).lower()=="log" else 1, horizontal=True)
        cal_lb = st.selectbox("Calendar lookback (years)", [str(w).upper() for w in windows if str(w).upper() != "ALL"] + ["ALL"], index=(2 if "10" in [str(w).upper() for w in windows] else 0))
        if st.button("🔄 Clear data cache & reload"):
            st.cache_data.clear()
            st.rerun()

    # Resolve artifacts
    base_df = _load_seasonality_base(ticker)

    # Diagnostics
    with st.expander("Diagnostics", expanded=False):
        base_path = SEAS_BASE_DIR / f"{ticker}.parquet"
        feat_path = FEATURES_DIR / f"{ticker}.parquet"
        st.write({
            "ticker": ticker,
            "base_path": str(base_path),
            "features_path": str(feat_path),
            "has_seasonality_base": base_df is not None and not base_df.empty,
            "has_features": feat_path.exists(),
        })

    # Display Last Data Date
    if base_df is not None and not base_df.empty and "date" in base_df.columns:
        last_dt = pd.to_datetime(base_df["date"]).max()
        st.info(f"Analysis based on data up to: **{last_dt.strftime('%Y-%m-%d')}**")

    # Guard rails: show clear hints if artifacts missing
    if base_df is None or base_df.empty:
        render_missing_artifact(
            section_title="Seasonality base artifacts are missing for this ticker.",
            path=SEAS_BASE_DIR / f"{ticker}.parquet",
            fix_hint=(
                "Run the following to generate seasonality base and facts:\n"
                f"python cli/mie.py build-seasonality-base --ticker {ticker}\n"
                f"python cli/mie.py build-seasonality-facts --ticker {ticker}"
            ),
        )
        st.stop()

    # Main: Seasonality vs Actual
    st.subheader("Seasonality vs. Actual (Cumulative)")
    try:
        curves_df, current_df, td_map = _compute_seasonal_curves(base_df, curves_lb, ret_type)
        if (curves_df is None or curves_df.empty) and (current_df is None or current_df.empty):
            render_empty_state("No seasonality curves computed", "Insufficient history for selected settings.")
        else:
            # Build Plotly line chart
            import plotly.graph_objects as go
            fig = go.Figure()
            # Historical curves
            if curves_df is not None and not curves_df.empty:
                for lb in sorted(curves_df["lookback"].unique().tolist(), key=lambda s: (s != "ALL", s)):
                    sub = curves_df[curves_df["lookback"] == lb].sort_values("doy_trading")
                    fig.add_trace(go.Scatter(
                        x=sub["doy_trading"], y=(sub["cum_ret"]*100.0), mode="lines",
                        name=f"{lb}", line=dict(color=_get_seasonality_color(lb)), hovertemplate="TD%{x}: %{y:.2f}%<extra>Avg {lb}</extra>",
                    ))
            # Current year path
            if current_df is not None and not current_df.empty:
                sub = current_df.sort_values("doy_trading")
                fig.add_trace(go.Scatter(
                    x=sub["doy_trading"], y=(sub["cum_ret"]*100.0), mode="lines",
                    name="Current", line=dict(color=_get_seasonality_color("current"), width=3), hovertemplate="TD%{x}: %{y:.2f}%<extra>Current</extra>",
                ))
            fig.update_layout(
                xaxis_title="Trading Day of Year (TD)", yaxis_title="Cumulative Return (%)",
                legend_title_text="Horizon",
                margin=dict(l=10, r=10, t=10, b=10), height=380,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"seasonality_chart_{ticker}")
    except Exception as e:
        render_exception("Failed to render Seasonality vs Actual", e)

    # Calendar Heatmap
    st.subheader("Seasonality Calendar (Average Same-Day Return)")
    try:
        pivot = _compute_calendar_table(base_df, lookback=str(cal_lb).upper(), min_valid_years=int(_load_seasonality_config().get("MIN_VALID_YEARS", 5)), return_type=str(ret_type).lower())
        if pivot is None or pivot.empty:
            render_empty_state("Calendar unavailable", "Not enough historical data for calendar view.")
        else:
            last_dt = None
            try:
                last_dt = pd.to_datetime(base_df["date"]).max() if "date" in base_df.columns else None
            except Exception:
                last_dt = None
            fig = _render_seasonality_calendar_image(ticker, str(cal_lb).upper(), pivot, last_dt)
            st.pyplot(fig, width="stretch")
    except Exception as e:
        render_exception("Failed to render Seasonality Calendar", e)

    # Drill-down section
    st.subheader("Drill-down: Selected Calendar Day")
    c1, c2, c3 = st.columns([1,1,6])
    with c1:
        sel_month = st.number_input("Month", min_value=1, max_value=12, value=max(1, pd.Timestamp.today().month))
    with c2:
        sel_day = st.number_input("Day", min_value=1, max_value=31, value=max(1, min(31, pd.Timestamp.today().day)))
    try:
        samples = _get_calendar_day_sample(ticker, str(cal_lb).upper(), int(sel_month), int(sel_day))
        st.caption(format_calendar_day_explanation(ticker, str(cal_lb).upper(), int(sel_month), int(sel_day), samples))
        if samples is None or samples.empty:
            render_empty_state("No occurrences", "No trading days for this calendar date under the chosen lookback.")
        else:
            # Drill-down table with formatted percent display for ret_pct
            drill_df = samples.copy()
            if "ret_pct" in drill_df.columns:
                # ret_pct is ALREADY in percent units — only format it
                styled_drill = drill_df.style.format({"ret_pct": "{:.2f}%"})
            else:
                styled_drill = drill_df
            st.dataframe(styled_drill, use_container_width=True)
            # Green/red bar chart for daily returns on this calendar day
            from plotly import graph_objects as go
            st.caption("Daily Returns on Selected Calendar Day")
            y_vals = drill_df["ret_pct"] if "ret_pct" in drill_df.columns else None
            if y_vals is not None:
                colors = ["green" if v >= 0 else "red" for v in y_vals]
                fig = go.Figure(data=[go.Bar(x=drill_df["year"], y=y_vals, marker=dict(color=colors))])
                fig.update_layout(
                    xaxis_title="year",
                    yaxis_title="%",
                    height=600,  # ~2–2.5× previous height
                    margin=dict(t=40, b=40, l=40, r=20),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No daily return data available for this calendar day.")
    except Exception as e:
        render_exception("Failed to render Drill-down", e)


# Entrypoint (Streamlit executes on import)
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        render_exception("Seasonality Analysis failed", e)
        raise
