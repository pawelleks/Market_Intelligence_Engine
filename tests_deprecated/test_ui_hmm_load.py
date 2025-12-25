import pandas as pd
import numpy as np
from pathlib import Path
from importlib import import_module
import json

DATA_DIR = Path("data")


def _write_minimal_hmm(ticker: str = "SPY"):
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=10)
    states = pd.DataFrame({
        "date": dates,
        "hmm_state": np.zeros(len(dates), dtype=int),
        "hmm_state_name": ["Bull"] * len(dates),
    })
    probs = pd.DataFrame({
        "date": dates,
        "hmm_prob_bull": np.full(len(dates), 0.7),
        "hmm_prob_bear": np.full(len(dates), 0.3),
    })
    meta = {"n_states": 2, "train_window_years": 5, "random_seed": 42}
    out = DATA_DIR / "analytics" / "hmm" / ticker
    out.mkdir(parents=True, exist_ok=True)
    states.to_parquet(out / "hmm_states.parquet", index=False)
    probs.to_parquet(out / "hmm_probs.parquet", index=False)
    (out / "hmm_metadata.json").write_text(json.dumps(meta))


def test_hmm_section_handles_present_and_missing(tmp_path, monkeypatch):
    # Ensure import of dashboard page
    mod = import_module("mie_lib.pages.regime_dashboard")

    # Write minimal HMM and features so the loader path doesn't error
    _write_minimal_hmm("SPY")
    # minimal features for price overlay
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=10)
    feats = pd.DataFrame({"date": dates, "adj_close": 100 + np.arange(len(dates))})
    (DATA_DIR / "features").mkdir(parents=True, exist_ok=True)
    feats.to_parquet(DATA_DIR / "features" / "SPY.parquet", index=False)

    # Call helpers to ensure no exceptions when files exist
    merged, probs = mod.load_price_and_hmm("SPY")
    assert merged is not None

    # Simulate missing by pointing to a fake ticker
    merged2, probs2 = mod.load_price_and_hmm("MISSING_TICK")
    # Should handle gracefully (returning (None, None))
    assert merged2 is None and probs2 is None

