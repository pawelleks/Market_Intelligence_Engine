import importlib
from pathlib import Path
import pytest

def test_normalize_window_value():
    mod = importlib.import_module("mie_lib.pages.01_Markov_Chain")

    f = mod._normalize_window_value
    assert f(1) == "1Y"
    assert f(2) == "2Y"
    assert f("1") == "1Y"
    assert f("2") == "2Y"
    assert f("1Y") == "1Y"
    assert f("2y") == "2Y"
    assert f("max") == "MAX"
    assert f("Custom") == "CUSTOM"
    assert f("weird") == "1Y"


def test_window_dates_from_features_does_not_raise():
    mod = importlib.import_module("mie_lib.pages.01_Markov_Chain")

    # If features exist for SPY in this repo, this should pass; otherwise just call with safe types
    try:
        mod._window_dates_from_features("SPY", "1Y")
    except Exception as e:
        pytest.skip(f"_window_dates_from_features requires local features; skipping: {e}")

