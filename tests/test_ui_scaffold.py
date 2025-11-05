from importlib import import_module

from app.ui.theme import get_tokens


def test_ui_tokens_load():
    tokens = get_tokens()
    assert "theme" in tokens and "behavior" in tokens
    assert "colors" in tokens["theme"]
    assert "font" in tokens["theme"]
    assert "chart" in tokens["theme"]
    assert tokens["theme"]["chart"]["max_points"] == 2500


def test_components_exist():
    mod = import_module("app.ui.components")
    for name in [
        "SectionHeader",
        "Card",
        "SummaryBox",
        "ExpandableChart",
        "DataStatus",
        "DownloadRow",
    ]:
        assert hasattr(mod, name)


def test_pages_import():
    # Ensure pages import without performing heavy IO
    for modname in [
        "app.pages.01_Market_Regime_Dashboard",
        "app.pages.02_Regime_Research_Lab",
        "app.pages.03_Alpha_Signals_Lab",
        "app.pages.04_Data_Control_Panel",
    ]:
        import_module(modname)

