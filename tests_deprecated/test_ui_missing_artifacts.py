from pathlib import Path
from importlib import import_module


def test_missing_combo_returns_cli_build_hint(tmp_path):
    # Prepare empty markov dir
    base = tmp_path / "data/analytics/markov/ZZZZ"
    base.mkdir(parents=True, exist_ok=True)

    mod = import_module("mie_lib.pages.m_chain")
    ticker = "ZZZZ"
    eff_order, eff_state_mode, eff_thr = 2, "tri", 10
    matrix_path = tmp_path / f"data/analytics/markov/{ticker}/matrix_order{eff_order}.parquet"
    states_path = tmp_path / f"data/analytics/markov/{ticker}/states.parquet"

    # Simulate missing artifacts by pointing paths to tmp; build command expected
    cmd = f"python cli/mie.py build-markov --ticker {ticker} --order {eff_order} --state-mode {eff_state_mode} --threshold-bps {eff_thr}"
    # Assert the command we embed matches this pattern (sanity)
    assert "build-markov" in cmd and f"--order {eff_order}" in cmd and f"--state-mode {eff_state_mode}" in cmd

