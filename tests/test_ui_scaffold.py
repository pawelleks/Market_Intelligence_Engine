from importlib import import_module

from mie_lib.ui.theme import get_tokens


def test_ui_tokens_load():
    tokens = get_tokens()
    assert "theme" in tokens and "behavior" in tokens
    assert "colors" in tokens["theme"]
    assert "font" in tokens["theme"]
    assert "chart" in tokens["theme"]
    assert tokens["theme"]["chart"]["max_points"] == 2500


def test_components_exist():
    mod = import_module("mie_lib.ui.components")
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
        "mie_lib.pages.regime_dashboard",
        "mie_lib.pages.research_lab",
        "mie_lib.pages.alpha_signals_lab",
        "mie_lib.pages.data_control_panel",
    ]:
        import_module(modname)

