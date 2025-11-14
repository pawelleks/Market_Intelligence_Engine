import importlib
from pathlib import Path
import pandas as pd
import numpy as np
import json
import subprocess
import sys


def _write_features(tmp_data: Path, ticker: str, rows: int = 200, seed: int = 0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=rows, freq="B")
    # shape returns so thresholds 5 vs 20 bps produce different labels
    ret = rng.normal(0, 0.01, size=rows) / 5.0
    df = pd.DataFrame({
        "date": dates,
        "ticker": ticker,
        "ret_1d": ret.astype(np.float32),
    })
    feat_dir = tmp_data / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(feat_dir / f"{ticker}.parquet", index=False)


def _sha1_bytes(path: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_binary_threshold_changes_matrix_values(monkeypatch, tmp_path):
    # Set up tmp data dir tree
    tmp_data = tmp_path / "data"
    tmp_data.mkdir(parents=True, exist_ok=True)
    ticker = "SPT"
    _write_features(tmp_data, ticker, rows=300)

    # Monkeypatch analytics modules to point to tmp data
    states_model = importlib.import_module("mie_lib.analytics.markov.states_model")
    markov_engine = importlib.import_module("mie_lib.analytics.markov.markov_engine")
    # Patch global paths
    states_model.DATA_DIR = tmp_data
    states_model.AN_MKV_DIR = tmp_data / "analytics" / "markov"
    markov_engine.DATA_DIR = tmp_data
    markov_engine.FEATURES_DIR = tmp_data / "features"
    markov_engine.ANALYTICS_DIR = tmp_data / "analytics" / "markov"

    # Build states for two thresholds
    from mie_lib.analytics.markov.states_model import build_states_from_features, derive_matrix
    build_states_from_features(ticker, 5, "binary")
    build_states_from_features(ticker, 20, "binary")

    # Derive matrices (order=1) for 1Y
    m5 = derive_matrix(ticker, 5, "binary", 1, "1Y")
    m20 = derive_matrix(ticker, 20, "binary", 1, "1Y")
    assert not m5.equals(m20), "Matrices for different thresholds should differ"

    p5 = tmp_data / f"analytics/markov/{ticker}/matrices/binary/thr5/order1/1Y.parquet"
    p20 = tmp_data / f"analytics/markov/{ticker}/matrices/binary/thr20/order1/1Y.parquet"
    assert p5.exists() and p20.exists()
    assert _sha1_bytes(p5) != _sha1_bytes(p20)

    # Check matrix metadata JSON contains thresholds
    meta_p = tmp_data / f"analytics/markov/{ticker}/matrices/binary/thr5/order1/matrix_metadata.json"
    assert meta_p.exists()
    meta = json.loads(meta_p.read_text())
    assert "1Y" in meta and meta["1Y"]["threshold_bps"] == 5


def test_cli_build_markov_writes_thresholded_paths(monkeypatch, tmp_path):
    tmp_data = tmp_path / "data"
    tmp_data.mkdir(parents=True, exist_ok=True)
    ticker = "SPT"
    _write_features(tmp_data, ticker, rows=250, seed=42)

    # Patch environment so cli uses tmp data dirs
    import mie_lib.cli.mie as me
    me.DATA_DIR = tmp_data
    me.FEATURES_DIR = tmp_data / "features"
    me.ANALYTICS_DIR = tmp_data / "analytics" / "markov"
    import mie_lib.analytics.markov.states_model as sm
    sm.DATA_DIR = tmp_data
    sm.AN_MKV_DIR = tmp_data / "analytics" / "markov"

    # Build via CLI: states then matrix (implicitly via grid)
    from mie_lib.cli.mie import main as mie_main
    # build-markov-states
    try:
        mie_main(["build-markov-states", "--ticker", ticker, "--state-modes", "binary", "--thresholds", "10"])
    except SystemExit:
        pass
    # derive-markov-matrix
    try:
        mie_main(["derive-markov-matrix", "--ticker", ticker, "--state-mode", "binary", "--threshold-bps", "10", "--order", "1", "--window", "1Y"])
    except SystemExit:
        pass

    # Expect the thresholded path
    p = tmp_data / f"analytics/markov/{ticker}/matrices/binary/thr10/order1/1Y.parquet"
    assert p.exists(), f"Expected matrix at {p}"
    # Metadata threshold
    meta_p = tmp_data / f"analytics/markov/{ticker}/matrices/binary/thr10/order1/matrix_metadata.json"
    assert meta_p.exists()
    meta = json.loads(meta_p.read_text())
    assert meta["1Y"]["threshold_bps"] == 10
