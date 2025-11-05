import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def features_tmp_dirs(tmp_path, monkeypatch, request):
    """Redirect RAW_DIR/FEATURES_DIR used by features builder to tmp_path during tests.
    Conditionally chdir to tmp for tests that expect relative data/ paths.
    """
    import importlib
    mod = importlib.import_module("src.features.build_features")
    # Patch module-level dirs for features module (writing isolated under tmp)
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path/"data", raising=True)
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path/"data"/"raw", raising=True)
    monkeypatch.setattr(mod, "FEATURES_DIR", tmp_path/"data"/"features", raising=True)
    # Ensure dirs exist
    (tmp_path/"data"/"raw").mkdir(parents=True, exist_ok=True)
    (tmp_path/"data"/"features").mkdir(parents=True, exist_ok=True)

    # Conditionally change CWD so tests that assert Path("data/...") find files under tmp
    fname = Path(str(request.node.fspath)).name
    needs_tmp = {"test_features.py", "test_features_update.py", "test_markov.py", "test_markov_sweep.py", "test_hmm.py", "test_timezone.py"}
    if fname in needs_tmp:
        monkeypatch.chdir(tmp_path)

    yield
