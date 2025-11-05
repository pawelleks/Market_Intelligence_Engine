import pandas as pd
from pathlib import Path
from importlib import import_module


def _write_parquet(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_legacy_ret_column_is_mapped_to_ret_1d(tmp_path, monkeypatch):
    # Arrange legacy features with 'date' and 'ret'
    ticker = "TESTL"
    feats_dir = tmp_path / "data/features"
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "ret": [0.0, 0.01, -0.02, 0.03, 0.0],
    })
    _write_parquet(df, feats_dir / f"{ticker}.parquet")

    mod = import_module("app.pages.01_Markov_Chain")
    loaded, remapped = mod._load_features_for_page(ticker, features_root=feats_dir)
    assert loaded is not None and not loaded.empty
    assert "ret_1d" in loaded.columns
    assert remapped is True
    # Sorted ascending and unique dates
    assert loaded["date"].is_monotonic_increasing
    assert not loaded["date"].duplicated().any()


def test_schema_ok_no_mapping_needed(tmp_path):
    ticker = "TESTN"
    feats_dir = tmp_path / "data/features"
    dates = pd.date_range("2021-01-01", periods=4, freq="D")
    df = pd.DataFrame({
        "date": dates[::-1],  # reverse order to check sort
        "ret_1d": [0.0, 0.01, 0.02, -0.01],
    })
    _write_parquet(df, feats_dir / f"{ticker}.parquet")

    mod = import_module("app.pages.01_Markov_Chain")
    loaded, remapped = mod._load_features_for_page(ticker, features_root=feats_dir)
    assert loaded is not None and not loaded.empty
    assert "ret_1d" in loaded.columns
    assert remapped is False
    # Sorted ascending and unique dates
    assert loaded["date"].is_monotonic_increasing
    assert not loaded["date"].duplicated().any()

