import importlib
from pathlib import Path
import pandas as pd
import numpy as np
import pytest


def _write_states(tmp_path: Path, ticker: str = "SPY", thr: int = 10, mode: str = "tri", days: int = 800):
    base = tmp_path / "data/analytics/markov" / ticker
    base.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    # simple oscillating states U/N/D
    states = np.random.choice(["U","N","D"], size=len(dates))
    df = pd.DataFrame({
        "date": dates,
        "state": states,
        "ret_1d": np.random.normal(0, 0.01, size=len(dates)),
        "thr_bps": thr,
        "state_mode": mode,
    })
    p = base / f"states_thr{thr}_{mode}.parquet"
    df.to_parquet(p, index=False)
    return p


def test_window_key_accepts_2y_and_path_format(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))

    # point data dir to tmp by monkeypatching module-level DATA_DIR
    sm = importlib.import_module("src.analytics.markov.states_model")
    monkeypatch.setattr(sm, "DATA_DIR", tmp_path / "data", raising=True)
    monkeypatch.setattr(sm, "AN_MKV_DIR", tmp_path / "data/analytics/markov", raising=True)

    ticker = "SPY"
    thr = 10
    mode = "tri"
    order = 1
    _write_states(tmp_path, ticker, thr, mode, days=800)

    # derive 2Y matrix
    df = sm.derive_matrix(ticker, thr, mode, order, "2Y")
    assert not df.empty
    # path exists
    p_cache = (tmp_path / f"data/analytics/markov/{ticker}/matrices/{mode}/thr{thr}/order{order}/2Y.parquet")
    assert p_cache.exists()


def test_cli_help_shows_2y(monkeypatch):
    # import CLI and check help text contains 2Y in derive-markov-matrix
    import subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    # Run help via python -m to use the workspace CLI module
    out = subprocess.check_output([sys.executable, "cli/mie.py", "derive-markov-matrix", "--help"]).decode()
    assert "1Y|2Y|5Y|10Y|20Y|MAX" in out

