import importlib
from pathlib import Path
import types
import pandas as pd
import numpy as np
import pytest

def test_get_ticker_from_state_variants(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    mod = importlib.import_module("app.pages.01_Markov_Chain")

    class ST:
        def __init__(self):
            self.session_state = {}
    st_ns = ST()

    def set_and_check(val, expect):
        st_ns.session_state.clear()
        st_ns.session_state["mk_ticker"] = val
        monkeypatch.setattr(mod, "st", st_ns, raising=True)
        out = mod._get_ticker_from_state("SPY")
        assert isinstance(out, str)
        assert out == expect

    set_and_check("SPY", "SPY")
    set_and_check(["qqq"], "QQQ")
    set_and_check(("iwm",), "IWM")
    set_and_check(pd.Series(["DIA"]), "DIA")
    set_and_check({"value": "spy"}, "SPY")
    set_and_check(None, "SPY")
    set_and_check("  ", "SPY")

