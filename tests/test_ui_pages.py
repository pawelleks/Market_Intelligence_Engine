from importlib import import_module
from pathlib import Path
import sys


def test_import_home_page(monkeypatch):
    # ensure repo root is on path
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    import_module("app.Home")


def test_import_dashboard_and_research(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    import_module("app.pages.01_Market_Regime_Dashboard")
    import_module("app.pages.02_Regime_Research_Lab")

