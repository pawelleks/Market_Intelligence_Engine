from pathlib import Path
import inspect
import math

import pandas as pd
import numpy as np

import mie_lib.analytics.markov.states_model as states_model

from mie_lib.analytics.markov.states_model import (
    _window_key_from_arg,
    build_states_from_features,
    states_for,
    derive_matrix,
    one_step,
)


def _write_features(tmp_path: Path, tkr: str = "TS1", days: int = 600):
    dates = pd.bdate_range("2020-01-01", periods=days)
    # synthetic lognormal-ish returns
    ret = pd.Series(np.random.normal(0, 0.01, size=len(dates)))
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
        "ticker": tkr,
    })
    (tmp_path / "data/features").mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp_path / f"data/features/{tkr}.parquet", index=False)


def test_states_then_matrices_cache_and_windows(tmp_path):
    _write_features(tmp_path, "TS1", days=800)

    # Build states once for tri/binary
    p_tri = build_states_from_features("TS1", 10, "tri")
    p_bin = build_states_from_features("TS1", 10, "binary")
    assert Path(p_tri).exists() and Path(p_bin).exists()

    # Load states
    tri_states = states_for("TS1", 10, "tri")
    bin_states = states_for("TS1", 10, "binary")
    assert set(tri_states.columns) >= {"date","state","ret_1d","thr_bps","state_mode"}

    # Derive K=1..3 for windows
    for K in [1,2,3]:
        m1 = derive_matrix("TS1", 10, "tri", K, "1Y")
        mM = derive_matrix("TS1", 10, "tri", K, "MAX")
        # caching idempotency
        m1b = derive_matrix("TS1", 10, "tri", K, "1Y")
        assert len(mM) >= len(m1) >= 1
        # row sums ~1
        sums = m1[[c for c in ["mc_prob_up","mc_prob_neutral","mc_prob_down"] if c in m1.columns]].sum(axis=1)
        assert (sums - 1.0).abs().max() < 1e-6
        # Laplace smoothing implies non-zero probs
        assert (m1[[c for c in ["mc_prob_up","mc_prob_neutral","mc_prob_down"] if c in m1.columns]] > 0).all().all()
        # idempotent cache
        assert m1.equals(m1b)

    # Path/window key round-trip
    assert _window_key_from_arg("1Y") == "1Y"
    assert _window_key_from_arg(("2021-01-01","2022-01-01")).startswith("CUSTOM_")

    # multi-step uses K=1-derived matrix
    mk1 = derive_matrix("TS1", 10, "tri", 1, "1Y")
    out = states_model.multi_step(mk1, [1, 2, 3], "tri")
    assert set(out.index) == {1, 2, 3}


def test_multi_step_distribution_progression():
    matrix_df = pd.DataFrame(
        {
            "context": ["U", "N", "D"],
            "mc_prob_up": [0.8, 0.3, 0.1],
            "mc_prob_neutral": [0.1, 0.5, 0.2],
            "mc_prob_down": [0.1, 0.2, 0.7],
            "counts": [100, 80, 60],
        }
    )
    horizons = [1, 2, 3, 4, 5]
    out = states_model.multi_step(matrix_df, horizons, "tri")
    assert list(out.index) == [1, 2, 3, 4, 5]
    # Ensure probabilities evolve over time for at least one state
    first_probs = out.loc[1].to_numpy()
    last_probs = out.loc[5].to_numpy()
    assert not np.allclose(first_probs, last_probs)
    # Probabilities remain normalized per horizon
    assert np.allclose(out.sum(axis=1).to_numpy(), 1.0)


def test_multi_step_no_ctx_row_keyword_and_progression():
    sig = inspect.signature(states_model.multi_step)
    assert "ctx_row" not in sig.parameters
    assert "mode" in sig.parameters

    matrix = pd.DataFrame(
        [
            {"context": "G", "mc_prob_up": 0.6, "mc_prob_neutral": 0.2, "mc_prob_down": 0.2, "counts": 10},
            {"context": "N", "mc_prob_up": 0.3, "mc_prob_neutral": 0.4, "mc_prob_down": 0.3, "counts": 5},
            {"context": "R", "mc_prob_up": 0.1, "mc_prob_neutral": 0.2, "mc_prob_down": 0.7, "counts": 8},
        ]
    )
    horizons = [1, 2, 3, 4, 5]
    result = states_model.multi_step(matrix, horizons, "tri")

    assert list(result.index) == sorted(set(horizons))
    assert "mc_prob_neutral" in result.columns
    assert not result.iloc[0].equals(result.iloc[-1])
    assert all(math.isclose(row.sum(), 1.0, rel_tol=1e-6) for _, row in result.iterrows())


