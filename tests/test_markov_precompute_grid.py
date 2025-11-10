import sys
from pathlib import Path
import importlib
import json
import hashlib
import pandas as pd
import numpy as np


def _write_features(tmp_data: Path, ticker: str, rows: int = 300, seed: int = 0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=rows, freq="B")
    # Construct returns with small, medium, and large moves for threshold sensitivity
    base = rng.normal(0, 0.01, size=rows)
    # Damp most values but inject larger spikes
    ret = base / 8.0
    ret[::37] += 0.004  # ~40bps up spikes
    ret[::53] -= 0.004  # ~40bps down spikes
    df = pd.DataFrame({
        "date": dates,
        "ticker": ticker,
        "ret_1d": ret.astype("float32"),
    })
    feat_dir = tmp_data / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(feat_dir / f"{ticker}.parquet", index=False)


def _sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_build_markov_grid_basic(monkeypatch, tmp_path):
    tmp_data = tmp_path / "data"
    tmp_data.mkdir(parents=True, exist_ok=True)
    # Two synthetic tickers
    for t, seed in [("TK1", 1), ("TK2", 2)]:
        _write_features(tmp_data, t, rows=300, seed=seed)

    # Patch analytics modules to use tmp data roots
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    me = importlib.import_module("src.analytics.markov.markov_engine")
    sm = importlib.import_module("src.analytics.markov.states_model")
    me.DATA_DIR = tmp_data
    me.FEATURES_DIR = tmp_data / "features"
    me.ANALYTICS_DIR = tmp_data / "analytics" / "markov"
    sm.DATA_DIR = tmp_data
    sm.AN_MKV_DIR = tmp_data / "analytics" / "markov"

    # Run CLI build-markov-grid over a small grid
    from cli.mie import main as mie_main
    args = [
        "build-markov-grid",
        "--tickers", "TK1,TK2",
        "--state-modes", "binary,tri",
        "--thresholds", "5,25",
        "--windows", "1Y,2Y",
        "--orders", "1,2",
    ]
    try:
        mie_main(args)
    except SystemExit:
        pass

    # Assert expected files exist for a sample combo
    p = tmp_data / "analytics/markov/TK1/matrices/binary/thr5/order1/1Y.parquet"
    q = tmp_data / "analytics/markov/TK1/matrices/tri/thr25/order2/2Y.parquet"
    assert p.exists(), f"Missing {p}"
    assert q.exists(), f"Missing {q}"

    # Schema checks
    dfp = pd.read_parquet(p)
    assert "context" in dfp.columns and "mc_prob_up" in dfp.columns and "mc_prob_down" in dfp.columns
    assert (dfp[[c for c in dfp.columns if c.startswith("mc_prob_")]].sum(axis=1) > 0.99).all()

    # Idempotency: run again
    try:
        mie_main(args)
    except SystemExit:
        pass
    # Files still valid
    dfp2 = pd.read_parquet(p)
    assert dfp2.equals(dfp)

    # No cross-threshold contamination: thr5 vs thr25 differ for binary if data supports
    p5 = tmp_data / "analytics/markov/TK1/matrices/binary/thr5/order1/1Y.parquet"
    p25 = tmp_data / "analytics/markov/TK1/matrices/binary/thr25/order1/1Y.parquet"
    assert p25.exists()
    # They may occasionally be close but should not be byte-identical for this synthetic shape
    assert _sha1(p5) != _sha1(p25), "Expected distinct parquet content across thresholds for binary"
