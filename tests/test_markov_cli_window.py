from importlib import import_module


def test_build_cli_for_combo_with_window(tmp_path, monkeypatch):
    # Import the page module
    mod = import_module("app.pages.01_Markov_Chain")
    # Call with a window to ensure the flag is included
    cmd = mod._build_cli_for_combo("SPY", 2, "tri", 10, window="5Y")
    assert "--window 5Y" in cmd
    # Call without a window to ensure no window flag present
    cmd2 = mod._build_cli_for_combo("SPY", 2, "tri", 10)
    assert "--window" not in cmd2

