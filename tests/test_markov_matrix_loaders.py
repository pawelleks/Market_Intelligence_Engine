import importlib
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

def _write_parquet(df, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_matrix_loader_exact_and_fallback(monkeypatch, tmp_path):
    mod = importlib.import_module("mie_lib.pages.m_chain")

    data_root = tmp_path / "data"
    # Build three distinct matrices
    p_bin10 = data_root / "analytics/markov/SPT/matrices/binary/thr10/order1/1Y.parquet"
    p_bin15 = data_root / "analytics/markov/SPT/matrices/binary/thr15/order1/1Y.parquet"
    p_tri10 = data_root / "analytics/markov/SPT/matrices/tri/thr10/order1/1Y.parquet"
    _write_parquet(pd.DataFrame({"context":["U","D"],"mc_prob_up":[0.9,0.1],"mc_prob_down":[0.1,0.9]}), p_bin10)
    _write_parquet(pd.DataFrame({"context":["U","D"],"mc_prob_up":[0.8,0.2],"mc_prob_down":[0.2,0.8]}), p_bin15)
    _write_parquet(pd.DataFrame({"context":["U","D"],"mc_prob_up":[0.7,0.3],"mc_prob_neutral":[0.2,0.2],"mc_prob_down":[0.1,0.5]}), p_tri10)

    # Monkeypatch DATA to tmp data root
    monkeypatch.setattr(mod, "DATA", data_root, raising=True)

    # Exact loads
    df10, info10 = mod._load_matrix_for_selection("SPT", "binary", 10, 1, "1Y", allow_fallback=False)
    df15, info15 = mod._load_matrix_for_selection("SPT", "binary", 15, 1, "1Y", allow_fallback=False)
    dfT, infoT = mod._load_matrix_for_selection("SPT", "tri", 10, 1, "1Y", allow_fallback=False)

    # Ensure different content between thresholds and modes
    assert not df10.equals(df15)
    assert not df10.equals(dfT)

    # Cache key must not return same object for different thresholds
    # Indirectly check by loading again and comparing a value unique to each
    df10b, _ = mod._load_matrix_for_selection("SPT", "binary", 10, 1, "1Y", allow_fallback=False)
    assert df10b.iloc[0]["mc_prob_up"] == 0.9
    assert df15.iloc[0]["mc_prob_up"] == 0.8

    # Fallback: request thr20 missing -> nearest available is 15
    df20, info20 = mod._load_matrix_for_selection("SPT", "binary", 20, 1, "1Y", allow_fallback=True)
    assert info20["resolved"]["thr"] == 15
    assert info20["fallback_used"] is True


