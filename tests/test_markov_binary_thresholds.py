import importlib
from pathlib import Path
import pandas as pd
import pytest
import inspect


def _write_parquet(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_binary_thresholds_load_distinct_matrices(monkeypatch, tmp_path):
    # Arrange tmp data root with two binary matrices for different thresholds

    mod = importlib.import_module("mie_lib.pages.m_chain")
    # Assert cache loader signature includes all key params
    sig = inspect.signature(mod._load_matrix_cached_by_params)
    assert all(k in sig.parameters for k in [
        "ticker", "mode", "thr", "order", "window", "path_str", "mtime"
    ]), "Cached loader must include all key params to avoid cross-threshold reuse"

    data_root = tmp_path / "data"
    tkr = "TK"
    p_thr10 = data_root / f"analytics/markov/{tkr}/matrices/binary/thr10/order1/1Y.parquet"
    p_thr15 = data_root / f"analytics/markov/{tkr}/matrices/binary/thr15/order1/1Y.parquet"

    df10 = pd.DataFrame({
        "context": ["U", "D"],
        "mc_prob_up": [0.90, 0.10],
        "mc_prob_down": [0.10, 0.90],
    })
    df15 = pd.DataFrame({
        "context": ["U", "D"],
        "mc_prob_up": [0.70, 0.30],
        "mc_prob_down": [0.30, 0.70],
    })
    _write_parquet(df10, p_thr10)
    _write_parquet(df15, p_thr15)

    # Point the page DATA root to tmp
    monkeypatch.setattr(mod, "DATA", data_root, raising=True)

    # Act: load exact matrices (no fallback)
    m10, info10 = mod._load_matrix_for_selection(tkr, "binary", 10, 1, "1Y", allow_fallback=False)
    m15, info15 = mod._load_matrix_for_selection(tkr, "binary", 15, 1, "1Y", allow_fallback=False)

    # Assert: matrices differ and resolved thresholds/paths are as requested
    assert not m10.equals(m15), "Expected distinct matrices for different thresholds in binary mode"
    assert info10["resolved"]["thr"] == 10
    assert info15["resolved"]["thr"] == 15
    assert str(info10["path"]).endswith("/matrices/binary/thr10/order1/1Y.parquet")
    assert str(info15["path"]).endswith("/matrices/binary/thr15/order1/1Y.parquet")
    assert not info10.get("fallback_used"), "No fallback should be used when exact file exists"
    assert not info15.get("fallback_used"), "No fallback should be used when exact file exists"

    # No legacy top-level matrix created; success implies windowed path used
    legacy = data_root / f"analytics/markov/{tkr}/matrix_order1.parquet"
    assert not legacy.exists(), "Test should not rely on legacy matrix_orderK parquet"
