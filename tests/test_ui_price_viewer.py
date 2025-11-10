import importlib
import pathlib

def test_price_viewer_import():
    # ensure module imports without Streamlit runtime error
    mod = importlib.import_module("app.pages.05_Price_and_Returns_Viewer")
    assert hasattr(mod, "main")

def test_price_viewer_helpers_exist():
    mod = importlib.import_module("app.pages.05_Price_and_Returns_Viewer")
    for name in ["_safe_read_raw", "_compute_daily_returns", "_normalize_price_df"]:
        assert hasattr(mod, name)

