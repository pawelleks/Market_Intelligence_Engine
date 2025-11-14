import sys
from pathlib import Path
from importlib import import_module
import re


def test_pages_exist_and_home_imports():
    root = Path(__file__).resolve().parents[1] / "src" / "mie_lib"

    pages = [
        root / "pages" / "01_Market_Regime_Dashboard.py",
        root / "pages" / "02_Regime_Research_Lab.py",
        root / "pages" / "03_Alpha_Signals_Lab.py",
        root / "pages" / "04_Data_Control_Panel.py",
    ]
    for p in pages:
        assert p.exists(), f"Missing page file: {p}"

    # Home should import cleanly
    import_module("mie_lib.Home")


def test_home_page_links_use_pages_relative():
    root = Path(__file__).resolve().parents[1]
    home = root / "src" / "mie_lib" / "Home.py"
    text = home.read_text()
    # Verify that st.page_link paths start with "pages/"
    for m in re.finditer(r"st\.page_link\(([^)]*)\)", text):
        # pull the first argument literal if present
        inside = m.group(1)
        # Accept variable, but look for string literal occurrences
        literals = re.findall(r"\"([^\"]+)\"|'([^']+)'", inside)
        for g1, g2 in literals:
            lit = g1 or g2
            if lit.endswith('.py'):
                assert lit.startswith("pages/"), f"st.page_link should use 'pages/...' but found: {lit}"
