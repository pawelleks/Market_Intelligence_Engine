from __future__ import annotations
import traceback
from pathlib import Path
import streamlit as st

# Streamlit-safe error panels — no inline hex, concise and actionable

def render_exception(section_title: str, exc: Exception, hint: str | None = None) -> None:
    """Render a visible error panel with short traceback.
    Do not raise; show actionable context per UI guidelines.
    """
    st.error(section_title)
    msg = f"{exc.__class__.__name__}: {exc}"
    st.caption(msg)
    try:
        tb = traceback.format_exc(limit=5)
        with st.expander("Details", expanded=False):
            st.code(tb)
    except Exception:
        pass
    if hint:
        st.info(hint)


def render_missing_artifact(section_title: str, path: Path | str, fix_hint: str) -> None:
    """Show a clear missing-artifact panel with an exact CLI hint."""
    st.warning(section_title)
    st.caption(f"Expected: {path}")
    st.write(fix_hint)


def render_empty_state(section_title: str, message: str) -> None:
    """Neutral empty-state panel."""
    st.info(section_title)
    st.caption(message)

