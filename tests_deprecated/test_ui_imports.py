import sys
from pathlib import Path
from importlib import import_module


def test_imports_ok_from_repo_root():
    # Import UI modules
    theme = import_module("mie_lib.ui.theme")
    components = import_module("mie_lib.ui.components")

    # Import pages
    import_module("mie_lib.pages.01_Market_Regime_Dashboard")
    import_module("mie_lib.pages.02_Regime_Research_Lab")
    import_module("mie_lib.pages.03_Alpha_Signals_Lab")
    import_module("mie_lib.pages.04_Data_Control_Panel")

    # Basic attribute checks
    assert hasattr(theme, "get_tokens")
    assert hasattr(components, "SectionHeader")
