# --- path shim: ensure project root on sys.path for `from app...`
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[2]  # parent of "app"
_ROOT_STR = str(_ROOT)
if _ROOT_STR not in sys.path:
    sys.path.insert(0, _ROOT_STR)
del _ROOT, _ROOT_STR

import json
from pathlib import Path
import streamlit as st

from app.ui.theme import get_tokens, css_inject
from app.ui.components import SectionHeader, Card, SummaryBox, DataStatus

DATA_DIR = Path("data")


def render():
    tokens = get_tokens()
    css_inject(tokens)

    st.title("Data Control Panel")

    SectionHeader("Dataset Registry", None)

    def body_registry():
        p = DATA_DIR / "meta" / "dataset_registry.json"
        if not p.exists():
            DataStatus("Registry not found", "warn")
            return
        try:
            reg = json.loads(p.read_text())
            st.json(reg)
        except Exception:
            DataStatus("Failed to parse registry", "error")
        SummaryBox("Placeholder: registry overview.")

    Card("Registry", None, body_registry)

    SectionHeader("Operations", None)

    def body_ops():
        st.button("Rebuild Features", disabled=True)
        st.button("Update Raw", disabled=True)
        st.button("Recompute Models", disabled=True)
        SummaryBox("Placeholder: operations will be wired later.")

    Card("Ops", None, body_ops)

    SectionHeader("Logs", None)

    def body_logs():
        p = DATA_DIR / "logs" / "features.log"
        if not p.exists():
            DataStatus("features.log not found", "warn")
            return
        tail = "\n".join(p.read_text().splitlines()[-100:])
        st.code(tail, language="text")
        SummaryBox("Placeholder: logs tail.")

    Card("Logs", None, body_logs)


if __name__ == "__main__":
    render()
