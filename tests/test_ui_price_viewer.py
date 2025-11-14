import importlib
import pathlib
import pandas as pd

from mie_lib.core.state_classification import classify_tri_state

def test_price_viewer_import():
    # ensure module imports without Streamlit runtime error
    mod = importlib.import_module("mie_lib.pages.05_Price_and_Returns_Viewer")
    assert hasattr(mod, "main")


def test_price_viewer_helpers_exist():
    mod = importlib.import_module("mie_lib.pages.05_Price_and_Returns_Viewer")
    for name in ["_safe_read_raw", "_compute_daily_returns", "_normalize_price_df"]:
        assert hasattr(mod, name)


def test_classification_module_boundary_cases():
    # threshold 10 bps -> 0.001
    assert classify_tri_state(0.0010, 10) == "Green"
    assert classify_tri_state(-0.0010, 10) == "Red"
    assert classify_tri_state(0.000999, 10) == "Neutral"
    assert classify_tri_state(-0.000999, 10) == "Neutral"
    # higher threshold makes previous green become neutral
    assert classify_tri_state(0.0010, 15) == "Neutral"
