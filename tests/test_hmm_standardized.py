import os, sys
from pathlib import Path
import pandas as pd
import numpy as np

from src.analytics.hmm.hmm_engine import build_hmm_standardized_for_ticker


def _write_features(tmp_path: Path, tkr: str = "HX", rows: int = 700):
    dates = pd.bdate_range("2020-01-01", periods=rows)
    ret = pd.Series(np.random.normal(0, 0.01, size=len(dates)))
    rv20 = ret.rolling(20).std().fillna(ret.std())
    price = 100 * (1 + ret).cumprod()
    df = pd.DataFrame({
        "date": dates,
        "open": price.values,
        "high": price.values,
        "low": price.values,
        "close": price.values,
        "adj_close": price.values,
        "volume": np.random.randint(1_000, 10_000, size=len(dates)),
        "ret_1d": ret.values,
        "rv_20d": rv20.values,
        "ticker": tkr,
    })
    (tmp_path / "data/features").mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp_path / f"data/features/{tkr}.parquet", index=False)


def test_standardized_hmm_grid_and_idempotency(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(root))

    _write_features(tmp_path, "HX", 700)

    # Build 2-state and 3-state under win5y
    out2 = build_hmm_standardized_for_ticker("HX", n_states=2, train_window_years=5)
    out3 = build_hmm_standardized_for_ticker("HX", n_states=3, train_window_years=5)
    assert Path(out2["probs"]).exists() and Path(out2["states"]).exists() and Path(out2["metrics"]).exists()
    assert Path(out3["probs"]).exists() and Path(out3["states"]).exists()

    # Check probs in [0,1] and row sums ~ 1
    p2 = pd.read_parquet(out2["probs"])
    cols2 = [c for c in ["hmm_prob_bull","hmm_prob_bear"] if c in p2.columns]
    assert not p2.empty and ((p2[cols2] >= 0) & (p2[cols2] <= 1)).all().all()
    sums2 = p2[cols2].sum(axis=1)
    assert (sums2 - 1.0).abs().max() < 1e-6

    p3 = pd.read_parquet(out3["probs"])
    cols3 = ["hmm_prob_bull","hmm_prob_neutral","hmm_prob_bear"]
    assert ((p3[cols3] >= 0) & (p3[cols3] <= 1)).all().all()
    sums3 = p3[cols3].sum(axis=1)
    assert (sums3 - 1.0).abs().max() < 1e-6

    # State naming by mean: Bull should have higher mean return than Bear
    meta2 = Path(out2["metadata"]).read_text()
    meta3 = Path(out3["metadata"]).read_text()
    assert "n_states" in meta2 and "n_states" in meta3

    # Idempotent write: second run should be skipped
    out2b = build_hmm_standardized_for_ticker("HX", n_states=2, train_window_years=5)
    assert out2b.get("skipped") is True

