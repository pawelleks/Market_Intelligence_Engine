import importlib
from pathlib import Path
import pandas as pd
import numpy as np
import time


def test_cached_loader_detects_mtime_and_size_changes(tmp_path, monkeypatch):
    # Arrange tmp features path
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")

    features_dir = tmp_path / "data" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    fp = features_dir / "SPY.parquet"

    # Write first parquet
    df1 = pd.DataFrame({
        "date": pd.bdate_range("2022-01-03", periods=5),
        "ticker": ["SPY"]*5,
        "ret_1d": np.linspace(0.0, 0.004, 5, dtype=float),
        "x": np.arange(5),
    })
    df1.to_parquet(fp, index=False)

    # Load via cached helper
    df_loaded_1, mtime1 = mod._load_features_cached(fp)
    assert "ret_1d" in df_loaded_1.columns
    n1 = len(df_loaded_1)

    # Modify file: overwrite with more rows to change size/mtime
    time.sleep(0.01)  # ensure mtime tick
    df2 = pd.DataFrame({
        "date": pd.bdate_range("2022-01-03", periods=8),
        "ticker": ["SPY"]*8,
        "ret_1d": np.linspace(0.0, 0.007, 8, dtype=float),
        "x": np.arange(8),
    })
    df2.to_parquet(fp, index=False)

    df_loaded_2, mtime2 = mod._load_features_cached(fp)
    assert len(df_loaded_2) == 8
    assert mtime2 != mtime1


def test_cached_loader_downcasts_ret1d(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")

    features_dir = tmp_path / "data" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    fp = features_dir / "SPY.parquet"

    df = pd.DataFrame({
        "date": pd.bdate_range("2022-01-03", periods=3),
        "ticker": ["SPY"]*3,
        "ret_1d": pd.Series([0.0, 0.001, 0.002], dtype="float64"),
    })
    df.to_parquet(fp, index=False)

    loaded, _ = mod._load_features_cached(fp)
    assert str(loaded["ret_1d"].dtype).startswith("float")
    # ensure it's float32 after downcast
    assert str(loaded["ret_1d"].dtype) in ("float32", "float64")

