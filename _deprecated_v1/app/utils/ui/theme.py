from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import streamlit as st

# Keep imports light; load YAML only when needed


def get_metric_labels() -> dict[str, str]:
    return {
        # HMM
        "hmm_prob_bull": "Bull probability",
        "hmm_prob_bear": "Bear probability",
        "hmm_prob_neutral": "Neutral probability",
        "hmm_state_name": "Market regime",
        # Markov Order Sweep (next-state)
        "mc_prob_up_next": "Probability: Up next",
        "mc_prob_down_next": "Probability: Down next",
        "mc_prob_neutral_next": "Probability: Neutral next",
        "latest_context": "Latest context",
        "order": "Order",
        "support_count": "Support count",
        "coverage_pct": "Coverage (%)",
        "low_confidence": "Low confidence",
        # Markov Matrix (current-state/context)
        "context": "Context",
        "mc_prob_up": "Probability: Up",
        "mc_prob_neutral": "Probability: Neutral",
        "mc_prob_down": "Probability: Down",
        # Features
        "ret_1d": "1-day return",
        "rv_20d": "20-day realized volatility",
    }


def get_tokens() -> Dict:
    """Load UI tokens from config/ui.yml with caching."""
    @st.cache_data(ttl=None, show_spinner=False)
    def _load() -> Dict:
        from mie_lib.utils.config import load_named_config
        tokens = load_named_config("ui")
        if not tokens or "theme" not in tokens or "behavior" not in tokens:
            raise RuntimeError("Invalid UI config: expected 'theme' and 'behavior' sections")
        return tokens

    return _load()


def _norm_colors(tokens: Dict) -> Dict[str, str]:
    """Normalize color keys to include green, red, blue, gray_text, fg, bg, grid."""
    c = tokens["theme"]["colors"]
    # Map/derive with required defaults
    green = c.get("green") or "#16a34a"
    red = c.get("red") or "#ef4444"
    blue = c.get("blue") or c.get("accent_blue") or "#3b82f6"
    gray_text = c.get("gray_text") or c.get("neutral") or c.get("text")
    fg = c.get("fg") or c.get("text")
    bg = c.get("bg") or c.get("page_bg")
    grid = c.get("grid")
    return {
        "green": green,
        "red": red,
        "blue": blue,
        "gray_text": gray_text,
        "fg": fg,
        "bg": bg,
        "grid": grid,
        # alias semantics
        "bull": green,
        "bear": red,
        "neutral": blue,
        # also expose existing
        "page_bg": c.get("page_bg", bg),
        "card_bg": c.get("card_bg", bg),
        "text": c.get("text", fg),
    }


def color_for_status(status: str) -> str:
    t = get_tokens()
    nc = _norm_colors(t)
    s = (status or "").strip().lower()
    if s in ("bull", "ok", "positive", "up"):
        return nc["green"]
    if s in ("neutral", "info", "warning"):
        return nc["blue"]
    if s in ("bear", "risk", "error", "down"):
        return nc["red"]
    return nc["fg"]


def mpl_palette_for_prob(order: tuple[str, ...] = ("up", "neutral", "down")) -> List[str]:
    t = get_tokens()
    nc = _norm_colors(t)
    m = {"up": nc["green"], "neutral": nc["blue"], "down": nc["red"]}
    return [m.get(k, nc["fg"]) for k in order]


def plotly_palette_for_prob(order: tuple[str, ...] = ("up", "neutral", "down")) -> List[str]:
    # same as mpl palette
    return mpl_palette_for_prob(order)


def css_inject(tokens: Dict | None = None):
    if tokens is None:
        tokens = get_tokens()
    colors = tokens["theme"]["colors"]
    font = tokens["theme"]["font"]
    radii = tokens["theme"].get("radii", {})

    css = f"""
    <style>
    html, body, .stApp {{
      background: {colors['page_bg']} !important;
      color: {colors['text']} !important;
      font-family: {font['family']}, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, 'Helvetica Neue', Arial, sans-serif;
    }}
    .card {{
      background: {colors['card_bg']};
      border-radius: {radii.get('card', 12)}px;
      padding: {tokens['theme']['spacing']['pad_md']}px;
      margin-bottom: {tokens['theme']['spacing']['pad_md']}px;
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .muted {{ opacity: 0.8; font-size: {font['size_small']}px; }}
    .small {{ font-size: {font['size_small']}px; }}
    .title {{ font-size: {font['size_title']}px; font-weight: 600; }}
    .accent {{ color: {colors['accent_blue']}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def mpl_style(fig, ax, tokens: Dict):
    """Apply a minimal dark style to a Matplotlib figure/axes."""
    nc = _norm_colors(tokens)
    colors = tokens["theme"]["colors"]
    font = tokens["theme"]["font"]

    if hasattr(fig, 'set_facecolor'):
        fig.set_facecolor(nc["bg"])  # page background
    if hasattr(ax, 'set_facecolor'):
        ax.set_facecolor(colors.get("card_bg", nc["bg"]))
    for spine in getattr(ax, 'spines', {}).values():
        spine.set_color(nc["grid"])  # grid color for spines
    if hasattr(ax, 'tick_params'):
        ax.tick_params(colors=nc["fg"], labelsize=font["size_small"])
    if hasattr(ax, 'xaxis') and hasattr(ax.xaxis, 'grid'):
        ax.grid(True, color=nc["grid"], alpha=0.3, linewidth=0.5)
    if hasattr(ax, 'yaxis') and hasattr(ax.yaxis, 'grid'):
        ax.grid(True, color=nc["grid"], alpha=0.3, linewidth=0.5)
    if hasattr(ax, 'title'):
        ax.title.set_color(nc["fg"])  # type: ignore


def fmt_pct(x: float, ndigits: int = 1) -> str:
    try:
        return f"{round(float(x) * 100, ndigits)}%"
    except Exception:
        return "NA%"
