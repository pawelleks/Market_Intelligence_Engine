from importlib import import_module
from pathlib import Path


def test_format_missing_features_msg_includes_cli_and_filename():
    mod = import_module("app.pages.01_Markov_Chain")
    ticker = "SPY"
    fp = Path("data/features/SPY.parquet")
    msg = mod._format_missing_features_msg(ticker, fp, ["ret_1d"])
    assert "Features unavailable for SPY" in msg
    assert str(fp) in msg
    assert "ret_1d" in msg
    assert "python cli/mie.py build-features --mode full" in msg
    assert "update-features --lookback 90" in msg


def test_format_missing_matrix_msg_legacy_build_markov():
    mod = import_module("app.pages.01_Markov_Chain")
    msg = mod._format_missing_matrix_msg("SPY", "tri", 10, 2, "5Y")
    assert "Markov matrix unavailable" in msg
    assert "ticker=SPY" in msg and "order=2" in msg and "state_mode=tri" in msg and "threshold_bps=10" in msg
    assert "python cli/mie.py build-markov --ticker SPY --order 2 --state-mode tri --threshold-bps 10" in msg
    # We do not append window to build-markov legacy command to preserve compatibility
    assert "--window" not in msg

