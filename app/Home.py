# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]  # project root (parent of "app")
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import streamlit as st
from pathlib import Path

from app.ui.theme import css_inject

st.set_page_config(page_title="Market Intelligence Engine", layout="wide", initial_sidebar_state="expanded")

css_inject()

st.title("Market Intelligence Engine")
st.write(
    "Offline-first dashboards and research tools. This UI reads precomputed outputs only; run CLI pipelines first to populate data."
)

pages_dir = Path(__file__).resolve().parent / "pages"
page_files = sorted([p for p in pages_dir.glob("*.py") if p.name != "__init__.py"])

st.subheader("Available pages")
for p in page_files:
    name = p.stem
    # Human-friendly title: strip numeric prefix and underscores
    title = name
    if "_" in title:
        title = title.split("_", 1)[1].replace("_", " ")
    if title[:2].isdigit() and title[2:3] == " ":
        title = title[3:]
    blurb = "Compact offline dashboard" if "Dashboard" in title else "Research and controls (read-only)"
    cols = st.columns([3, 1])
    with cols[0]:
        st.write(f"- {title}")
        st.caption(blurb)
    with cols[1]:
        rel_path = f"pages/{p.name}"
        if hasattr(st, "page_link"):
            st.page_link(rel_path, label="Open page")
        else:
            st.caption(f"Open via: streamlit run {rel_path}")
