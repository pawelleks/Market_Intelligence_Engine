import json
from pathlib import Path
from importlib import import_module
import importlib  # added for explicit import_module usage
import pandas as pd


def test_param_derivation_and_headline(tmp_path):
    # Arrange a fake markov directory with a matrix_order1 and metadata


    mdir = tmp_path / "data/analytics/markov/SPY"
    mdir.mkdir(parents=True, exist_ok=True)

    # minimal matrix_order1 with context + probs and dates
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=3, freq="D"),
        "context": ["U", "N", "D"],
        "mc_prob_up": [0.6, 0.3, 0.2],
        "mc_prob_neutral": [0.2, 0.4, 0.3],
        "mc_prob_down": [0.2, 0.3, 0.5],
    })
    df.to_parquet(mdir / "matrix_order1.parquet", index=False)

    meta = {"order": 1, "state_mode": "tri", "threshold_bps": 12}
    (mdir / "metadata.json").write_text(json.dumps(meta))

    # Import module under test
    mod = importlib.import_module("mie_lib.pages.m_chain")
    # Derive params preferring control order if available
    eff = mod._derive_effective_params(meta, {"order": 1, "state_mode": "tri", "threshold_bps": 10}, {1})
    assert eff == (1, "tri", 10)

    # If control order not available, fall back to meta
    eff2 = mod._derive_effective_params(meta, {"order": 3, "state_mode": "tri", "threshold_bps": 10}, {1})
    assert eff2[0] == 1 and eff2[1] == "tri" and isinstance(eff2[2], int)

    # Headline builder returns non-empty string and does not rely on globals
    sub = mod._headline_subline("SPY", ("2020-01-01", "2020-01-03"), "tri", 12, 1)
    assert isinstance(sub, str) and len(sub) > 0
