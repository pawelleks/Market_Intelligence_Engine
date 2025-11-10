from __future__ import annotations

from typing import Callable, List, Tuple, Optional, Dict, Literal
import streamlit as st

from .theme import get_tokens, color_for_status, mpl_palette_for_prob


def SectionHeader(title: str, context_line: Optional[str] = None):
    st.markdown(f"<div class='title'>{title}</div>", unsafe_allow_html=True)
    if context_line:
        st.markdown(f"<div class='muted'>{context_line}</div>", unsafe_allow_html=True)


def Card(title: str, context: Optional[str], body_fn: Callable[[], None]):
    tokens = get_tokens()
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='title'>{title}</div>", unsafe_allow_html=True)
        if context:
            st.markdown(f"<div class='muted'>{context}</div>", unsafe_allow_html=True)
        body_fn()
        st.markdown("</div>", unsafe_allow_html=True)


def SummaryBox(text: str, status: Optional[Literal["bull","bear","neutral","info","warning","error"]] = None):
    color = color_for_status(status or "") if status else get_tokens()["theme"]["colors"]["text"]
    st.markdown(
        f"<div class='card small' style='border-left: 4px solid {color}; padding-left: 10px;'>{text}</div>",
        unsafe_allow_html=True,
    )


def ExpandableChart(render_fn: Callable[[dict], None], tokens: dict, series_kinds: Optional[Dict[str, Literal["bull","bear","neutral"]]] = None):
    # Render a small placeholder and an expandable area below
    with st.container():
        render_fn(tokens)
        with st.expander("Expand", expanded=False):
            render_fn(tokens)


def DataStatus(message: str, level: str = "info"):
    level_l = (level or "info").lower()
    color = color_for_status({
        "info": "neutral",
        "ok": "bull",
        "warn": "neutral",
        "warning": "neutral",
        "error": "bear",
        "risk": "bear",
    }.get(level_l, "neutral"))
    # Render using Streamlit built-ins but maintain color semantics via emoji prefix
    if level_l in ("warn", "warning"):
        st.warning(message)
    elif level_l == "error":
        st.error(message)
    else:
        st.info(message)


def DownloadRow(files: List[Tuple[str, str]]):
    tokens = get_tokens()
    cols = st.columns(len(files)) if files else []
    for (label, path), col in zip(files, cols):
        import os
        if os.path.exists(path):
            with col:
                st.download_button(label=f"Download {label}", data=open(path, "rb"), file_name=path.split("/")[-1])
        else:
            with col:
                st.button(label=f"{label} (missing)", disabled=True)


# New helpers

def plot_mpl(fig, caption: str|None=None):
    """Standard render for matplotlib figures in dashboard."""
    import streamlit as st
    st.pyplot(fig, width="stretch")
    if caption:
        st.caption(caption)


def apply_friendly_labels(df, labels: Dict[str, str]):
    """Return a NEW dataframe with columns renamed using labels (non-destructive)."""
    return df.rename(columns=lambda c: labels.get(c, c)).copy()


def fmt_percent_two_decimals(x) -> str:
    try:
        return f"{float(x) * 100:.2f}%"
    except Exception:
        return "NA%"


# Offline-safe loaders (no exceptions in UI)
from pathlib import Path
import pandas as _pd
import json as _json


def read_parquet_safe(path: Path):
    try:
        if path.exists():
            return _pd.read_parquet(path)
    except Exception:
        return None
    return None


def read_csv_safe(path: Path):
    try:
        if path.exists():
            return _pd.read_csv(path)
    except Exception:
        return None
    return None


def read_json_safe(path: Path):
    try:
        if path.exists():
            return _json.loads(path.read_text())
    except Exception:
        return None
    return None


def fmt_percent_one_decimal(x) -> str:
    try:
        return f"{float(x) * 100:.1f}%"
    except Exception:
        return "NA%"


def section_header(title: str):
    st.markdown(f"<div class='title'>{title}</div>", unsafe_allow_html=True)


def settings_line(*, ticker: str, window: str, mode: str, thr_bps: int, order: int, start: str, end: str, last_updated: str) -> str:
    """Return a compact settings line for screenshot-friendly context."""
    return (
        f"Settings: Ticker: {ticker} • Time range: {window} • Source: offline • State mode: {mode} "
        f"• Threshold: {thr_bps}bps • Order: {order} • Data set for {ticker}: {start} – {end} • Last updated: {last_updated}"
    )


def badge_state(name: str) -> str:
    """Return an inline HTML span for Green/Neutral/Red labels with theme colors.
    Avoid inline hex literals (all colors sourced from theme tokens).
    """
    tokens = get_tokens()
    colors = tokens["theme"]["colors"]
    # Source semantic colors with safe fallbacks referencing existing token keys only
    green = colors.get("green") or colors.get("bull") or colors.get("accent_blue") or colors.get("text")
    neutral = colors.get("blue") or colors.get("accent_blue") or colors.get("neutral") or colors.get("text")
    red = colors.get("red") or colors.get("bear") or colors.get("accent_blue") or colors.get("text")
    fg = colors.get("text")
    card_bg = colors.get("card_bg") or colors.get("page_bg") or fg
    name_l = (name or "").strip().lower()
    if name_l.startswith("green"):
        col = green; label = "Green"
    elif name_l.startswith("neutral"):
        col = neutral; label = "Neutral"
    elif name_l.startswith("red") or name_l.startswith("bear"):
        col = red; label = "Red"
    else:
        col = fg; label = name or ""
    return (
        f"<span style='display:inline-block;padding:1px 6px;border-radius:6px;" \
        f"background:{card_bg};border:1px solid rgba(255,255,255,0.08);color:{col};font-weight:600;'>" \
        f"{label}</span>"
    )
