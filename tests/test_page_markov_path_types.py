import importlib
from pathlib import Path
import pytest


def test_base_path_builds_for_spy_and_qqq(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")
    for ticker in ["SPY", "QQQ"]:
        base = mod._build_markov_base_path(ticker)
        assert isinstance(base, Path)
        assert base.is_absolute()
        assert str(base).endswith(f"markov/{ticker}")


def test_base_path_raises_for_int_ticker(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")
    with pytest.raises(ValueError) as ei:
        mod._build_markov_base_path(1)  # type: ignore[arg-type]
    assert "ticker must be a string symbol" in str(ei.value)

