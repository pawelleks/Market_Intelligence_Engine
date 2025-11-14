from pathlib import Path
import importlib
import pytest

def test_safe_width_monotonic(monkeypatch):
    mod = importlib.import_module("mie_lib.pages.m_chain")

    assert mod._safe_width(None) == "stretch"
    assert mod._safe_width(0) == "stretch"
    assert mod._safe_width(100) == 300
    assert mod._safe_width(400) == 400
    assert mod._safe_width("content") == "content"
    assert mod._safe_width("stretch") == "stretch"

