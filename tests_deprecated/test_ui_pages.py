from importlib import import_module
from pathlib import Path
import sys


def test_import_home_page():
    import_module("mie_lib.Home")


def test_import_dashboard_and_research():
    import_module("mie_lib.pages.01_Market_Regime_Dashboard")
    import_module("mie_lib.pages.01_Market_Regime_Dashboard")
    import_module("mie_lib.pages.02_Regime_Research_Lab")
