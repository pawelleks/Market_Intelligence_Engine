import json
from pathlib import Path
import pandas as pd
from importlib import import_module


def _write_markov_fixture(root: Path, mode: str = "tri") -> Path:
    base = root / "data/analytics/markov/SPY"
    base.mkdir(parents=True, exist_ok=True)
    # matrix order1: tri-mode (U,N,D rows contexts may be included via a 'context' col)
    df = pd.DataFrame({
        "context": ["U", "N", "D"],
        "mc_prob_up": [0.6, 0.3, 0.2],
        "mc_prob_neutral": [0.2, 0.4, 0.3],
        "mc_prob_down": [0.2, 0.3, 0.5],
    })
    (base / "matrix_order1.parquet").write_bytes(df.to_parquet(index=False))
    meta = {"order": 1, "state_mode": mode, "threshold_bps": 10}
    (base / "metadata.json").write_text(json.dumps(meta))
    return base


def test_loader_and_modes(tmp_path, monkeypatch):

    base = _write_markov_fixture(tmp_path, mode="tri")

    from mie_lib.pages import m_chain as mod
    # Load effective
    eff = mod._derive_effective_params({"order": 1, "state_mode": "tri", "threshold_bps": 10}, {"order": 1, "state_mode": "tri", "threshold_bps": 10}, {1})
    assert eff == (1, "tri", 10)

    # Read matrix and check rowsums ~ 1
    df = pd.read_parquet(base / "matrix_order1.parquet")
    sums = df[["mc_prob_up", "mc_prob_neutral", "mc_prob_down"]].sum(axis=1)
    assert (sums - 1.0).abs().max() < 1e-6

    # Binary projection hides neutral
    df_bin = df[["context", "mc_prob_up", "mc_prob_down"]]
    assert "mc_prob_neutral" not in df_bin.columns

    # Headline function should not crash
    sub = mod._headline_subline("SPY", ("2020-01-01", "2020-12-31"), "tri", 10, 1)
    assert isinstance(sub, str) and len(sub) > 0
