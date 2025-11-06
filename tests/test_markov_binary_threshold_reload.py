import importlib
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

def _write_parquet(df, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_binary_threshold_changes_reload(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")

    data_root = tmp_path / "data"
    # two binaries with different values
    base10 = data_root / "analytics/markov/TST/matrices/binary/thr10/order1/1Y.parquet"
    base20 = data_root / "analytics/markov/TST/matrices/binary/thr20/order1/1Y.parquet"
    df10 = pd.DataFrame({"context":["U","D"],"mc_prob_up":[0.9,0.1],"mc_prob_down":[0.1,0.9]})
    df20 = pd.DataFrame({"context":["U","D"],"mc_prob_up":[0.7,0.3],"mc_prob_down":[0.3,0.7]})
    _write_parquet(df10, base10)
    _write_parquet(df20, base20)

    # Point the page at tmp data root
    monkeypatch.setattr(mod, "DATA", data_root, raising=True)

    m10, info10 = mod._load_matrix_for_selection("TST", "binary", 10, 1, "1Y", allow_fallback=False)
    m20, info20 = mod._load_matrix_for_selection("TST", "binary", 20, 1, "1Y", allow_fallback=False)

    assert not m10.equals(m20), "Matrices for different thresholds must differ and be loaded distinctly"
    # Ensure resolved params reflect the thresholds used
    assert info10["resolved"]["thr"] == 10
    assert info20["resolved"]["thr"] == 20

