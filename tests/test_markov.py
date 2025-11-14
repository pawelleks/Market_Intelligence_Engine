import os
from pathlib import Path

import numpy as np
import pandas as pd

from mie_lib.features.build_features import build_features_for_ticker
from mie_lib.analytics.markov.markov_engine import MarkovConfig, build_markov_for_ticker

# Project paths
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
FEATURES_DIR = DATA_DIR / "features"


def _make_features_for_test(ticker: str = "MKV", days: int = 300):
    # synthetic raw
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    price = 100 + np.cumsum(np.random.normal(0, 0.5, size=len(dates)))
    raw = pd.DataFrame(
        {
            "date": dates,
            "open": price + np.random.normal(0, 0.1, size=len(dates)),
            "high": price + np.random.normal(0.1, 0.2, size=len(dates)),
            "low": price - np.random.normal(0.1, 0.2, size=len(dates)),
            "close": price + np.random.normal(0, 0.1, size=len(dates)),
            "adj_close": price,
            "volume": np.random.randint(1_000_000, 5_000_000, size=len(dates)),
            "ticker": ticker,
        }
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(RAW_DIR / f"{ticker}.parquet", index=False)
    # build features full
    build_features_for_ticker(ticker, mode="full", lookback=90, write_csv=False)


def test_markov_outputs_and_probs_sum():
    ticker = "MKV"
    _make_features_for_test(ticker, days=300)

    cfg = MarkovConfig(order=2, state_mode="tri", threshold_bps=10, min_samples_per_state=5)
    res = build_markov_for_ticker(ticker, cfg)
    out_dir = Path(res["out_dir"])

    # load matrix and counts
    mat = pd.read_parquet(out_dir / "matrix_order2.parquet")
    cnt = pd.read_parquet(out_dir / "counts_order2.parquet")
    assert "context" in mat.columns

    # rows sum to 1 within tolerance
    prob_cols = [c for c in mat.columns if c.startswith("mc_prob_")]
    s = mat[prob_cols].sum(axis=1)
    assert np.all(np.isfinite(s))
    assert np.all((np.abs(s - 1.0) <= 0.01) | (mat[prob_cols].isna().all(axis=1)))

    # non-negative
    assert (mat[prob_cols] >= 0).all().all()

    # predictions exist for dates after warm-up
    pred = pd.read_parquet(out_dir / "predictions.parquet")
    assert "date" in pred.columns
    assert len(pred) >= len(pd.read_parquet(FEATURES_DIR / f"{ticker}.parquet")) - cfg.order

    # metadata
    meta = (out_dir / "metadata.json").read_text()
    assert str(cfg.order) in meta and cfg.state_mode in meta and str(cfg.threshold_bps) in meta

    # idempotency
    res2 = build_markov_for_ticker(ticker, cfg)
    mat2 = pd.read_parquet(out_dir / "matrix_order2.parquet")
    assert mat.equals(mat2)

    # cleanup
    (RAW_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    (FEATURES_DIR / f"{ticker}.parquet").unlink(missing_ok=True)
    for fn in ["states.parquet", "matrix_order2.parquet", "counts_order2.parquet", "predictions.parquet", "metadata.json"]:
        (out_dir / fn).unlink(missing_ok=True)
    try:
        out_dir.rmdir()
    except OSError:
        pass
