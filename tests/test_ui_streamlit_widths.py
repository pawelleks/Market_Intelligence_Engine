from pathlib import Path
import importlib
import pytest

def test_safe_width_monotonic(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")

    assert mod._safe_width(None) == "stretch"
    assert mod._safe_width(0) == "stretch"
    assert mod._safe_width(100) == 300
    assert mod._safe_width(400) == 400
    assert mod._safe_width("content") == "content"
    assert mod._safe_width("stretch") == "stretch"

