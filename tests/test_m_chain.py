from __future__ import annotations
from pathlib import Path
import sys
import types
import pandas as pd
import pytest
import importlib

# Ensure src-layout import
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    # Import fresh module instance
    m = importlib.import_module("mie_lib.pages.m_chain")
    importlib.reload(m)

    # Point DATA to a per-test temp tree
    data_root = tmp_path / "data"
    monkeypatch.setattr(m, "DATA", data_root, raising=True)
    return m


@pytest.fixture()
def fake_read_parquet(monkeypatch):
    calls = []

    def _fake(path, *a, **k):
        calls.append(Path(path))
        # Return a tiny DataFrame to simulate a matrix
        return pd.DataFrame({"context": ["A-B-C"], "value": [1.0]})

    monkeypatch.setattr("pandas.read_parquet", _fake, raising=True)
    return calls


def _touch_matrix_file(base_dir: Path, ticker="SPY", mode="close", thr=50, order=1, window="1D"):
    p = base_dir / "analytics" / "markov" / ticker / "matrices" / mode / f"thr{thr}" / f"order{order}" / f"{window}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def test_matrix_exact_path(mod, tmp_path):
    p = mod._matrix_exact_path("SPY", "CLOSE", 50, 1, "1d")
    assert str(p).endswith("data/analytics/markov/SPY/matrices/close/thr50/order1/1D.parquet")


def test_nearest_available_threshold_prefers_smallest_distance_then_value(mod, tmp_path):
    base = mod.DATA
    _touch_matrix_file(base, thr=40)
    _touch_matrix_file(base, thr=80)
    near = mod._nearest_available_threshold("SPY", "close", 1, "1D", 60)
    # Distances: 20 vs 20 -> pick smaller value (40)
    assert near == 40


def test_nearest_available_threshold_none_when_no_dir(mod):
    assert mod._nearest_available_threshold("SPY", "close", 1, "1D", 60) is None


def test_load_matrix_for_selection_exact(fake_read_parquet, mod, tmp_path):
    expected = _touch_matrix_file(mod.DATA, thr=50)
    df, info = mod._load_matrix_for_selection("SPY", "close", 50, 1, "1D", allow_fallback=True)
    assert not info["fallback_used"]
    assert info["resolved"]["thr"] == 50
    assert fake_read_parquet[-1] == expected
    assert not df.empty


def test_load_matrix_for_selection_fallback_to_nearest(fake_read_parquet, mod, tmp_path):
    expected = _touch_matrix_file(mod.DATA, thr=50)  # only 50 exists
    df, info = mod._load_matrix_for_selection("SPY", "close", 60, 1, "1D", allow_fallback=True)
    assert info["fallback_used"]
    assert info["resolved"]["thr"] == 50
    assert fake_read_parquet[-1] == expected
    assert not df.empty


def test_load_matrix_for_selection_raises_when_missing_and_no_fallback(mod):
    with pytest.raises(FileNotFoundError):
        mod._load_matrix_for_selection("SPY", "close", 60, 1, "1D", allow_fallback=False)


def test_load_matrix_cached_by_params_uses_path(fake_read_parquet, mod, tmp_path):
    p = _touch_matrix_file(mod.DATA, thr=100)
    df = mod._load_matrix_cached_by_params("SPY", "close", 100, 1, "1D", str(p), p.stat().st_mtime)
    assert fake_read_parquet[-1] == p
    assert not df.empty


def test_as_context_key_from_list(mod):
    key = mod._as_context_key(["A", "B", "C"])
    assert key == "A-B-C"


def test_find_context_row(mod):
    df = pd.DataFrame({"context": ["X-Y", "A-B-C"], "value": [0, 1]})
    row = mod._find_context_row(df, "A-B-C")
    assert row is not None and row["value"] == 1


def test_safe_width(mod):
    assert mod._safe_width(None) == "stretch"
    assert mod._safe_width(0) == "stretch"
    assert mod._safe_width(250) == 300
    assert mod._safe_width(600) == 600
    assert mod._safe_width("75%") == "75%"


def test_get_ticker_from_state_default(mod):
    assert mod._get_ticker_from_state() == "SPY"


def test_get_ticker_from_state_from_session(monkeypatch, mod):
    dummy = types.SimpleNamespace(session_state={"ticker": "aapl"})
    monkeypatch.setitem(mod.__dict__, "st", dummy)
    assert mod._get_ticker_from_state(default="MSFT") == "AAPL"
