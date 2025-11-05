import json
from pathlib import Path
import pandas as pd
import numpy as np
from importlib import import_module


def _fixture_markov(root: Path, mode: str = "tri") -> Path:
    base = root / "data/analytics/markov/SPY"
    base.mkdir(parents=True, exist_ok=True)
    # states
    dates = pd.date_range("2020-01-01", periods=5)
    states = pd.DataFrame({"date": dates, "mc_state_today": ["U","N","D","U","N"]})
    states.to_parquet(base / "states.parquet", index=False)
    # matrix order1
    mat = pd.DataFrame({
        "context": ["U","N","D"],
        "mc_prob_up": [0.6,0.3,0.2],
        "mc_prob_neutral": [0.2,0.4,0.3],
        "mc_prob_down": [0.2,0.3,0.5],
    })
    mat.to_parquet(base / "matrix_order1.parquet", index=False)
    # metadata
    meta = {"order": 1, "state_mode": mode, "threshold_bps": 10}
    (base / "metadata.json").write_text(json.dumps(meta))
    # features for window
    fdir = root / "data/features"
    fdir.mkdir(parents=True, exist_ok=True)
    feats = pd.DataFrame({"date": pd.date_range("2019-01-01", periods=400)})
    feats.to_parquet(fdir / "SPY.parquet", index=False)
    return base


def test_binary_vs_tri_shapes_and_rowsums(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    base = _fixture_markov(tmp_path, mode="tri")

    mod = import_module("app.pages.01_Markov_Chain")
    mat = pd.read_parquet(base / "matrix_order1.parquet")
    tri = mod._project_matrix_for_mode(mat, "tri")
    assert all(c in tri.columns for c in ["mc_prob_up","mc_prob_neutral","mc_prob_down"])  # tri has neutral
    bin_ = mod._project_matrix_for_mode(mat, "binary")
    assert "mc_prob_neutral" not in bin_.columns  # binary drops neutral

    sums = tri[["mc_prob_up","mc_prob_neutral","mc_prob_down"]].sum(axis=1)
    assert np.allclose(sums.values, 1.0)


def test_context_backoff_and_multistep(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    base = _fixture_markov(tmp_path, mode="tri")
    mod = import_module("app.pages.01_Markov_Chain")

    states = pd.read_parquet(base / "states.parquet")
    ctx, seq = mod._build_context(states, 3, states['date'].min().date(), states['date'].max().date())
    # backoff should still find a row for shorter contexts
    row = mod._find_context_row(pd.read_parquet(base / "matrix_order1.parquet"), ctx or "")
    assert row is not None

    # multistep uses K=1 matrix only
    k1 = pd.read_parquet(base / "matrix_order1.parquet")
    pi_row = row
    mult = mod._compute_multistep(pi_row, k1, [1,2,3], "tri")
    assert not mult.empty and set(mult.index) == {1,2,3}

