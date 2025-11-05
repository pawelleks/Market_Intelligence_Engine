import importlib
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

def test_as_context_key_and_find_row(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")

    # Build dummy matrix with a context column to mirror page expectations
    mat = pd.DataFrame({
        "context": ["G", "N", "R", "GN"],
        "mc_prob_up": [0.7, 0.3, 0.2, 0.6],
        "mc_prob_neutral": [0.2, 0.5, 0.3, 0.2],
        "mc_prob_down": [0.1, 0.2, 0.5, 0.2],
    })

    def pick(x):
        key = mod._as_context_key(x)
        r = mod._find_context_row(mat, key)
        assert r is None or isinstance(r, pd.Series)
        return r

    assert mod._as_context_key("G-N") == "G-N"
    assert mod._as_context_key(["G","N"]) == "G-N"
    assert mod._as_context_key(np.array(["G","N"])) == "G-N"
    assert mod._as_context_key(pd.Series(["G","N"])) == "G-N"
    assert mod._as_context_key(None) == ""
    assert mod._as_context_key(123) == ""

    # Existing single-token rows
    assert pick("G")["context"] == "G"
    assert pick(["N"]).get("context") == "N"
    # Backoff: if not exact, find first (helper handles fallback)
    assert isinstance(mod._safe_pick_context_row(mat, mod._as_context_key(["G","N"])), pd.Series)

