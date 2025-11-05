import sys
from pathlib import Path
from importlib import import_module


def test_imports_ok_from_repo_root(monkeypatch):
    # Ensure repo root is on sys.path for the test context
    here = Path(__file__).resolve()
    root = here.parent.parent
    monkeypatch.syspath_prepend(str(root))

    # Import UI modules
    theme = import_module("app.ui.theme")
    components = import_module("app.ui.components")

    # Import pages
    import_module("app.pages.01_Market_Regime_Dashboard")
    import_module("app.pages.02_Regime_Research_Lab")
    import_module("app.pages.03_Alpha_Signals_Lab")
    import_module("app.pages.04_Data_Control_Panel")

    # Basic attribute checks
    assert hasattr(theme, "get_tokens")
    assert hasattr(components, "SectionHeader")
