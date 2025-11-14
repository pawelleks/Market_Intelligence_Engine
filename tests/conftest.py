from __future__ import annotations
import importlib
import os
from pathlib import Path
import pytest
print("conftest.py loaded")


@pytest.fixture(autouse=True)
def _patch_data_roots(tmp_path, monkeypatch, request):
    """
    For every test, ensure modules read/write under an isolated tmp data dir:
      tmp_path/data/{features,raw,analytics}
    We monkeypatch module-level constants so callers that import them
    (e.g., FEATURES_DIR) point into tmp.
    """
    print("_patch_data_roots started")
    base = tmp_path / "data"
    features = base / "features"
    raw = base / "raw"
    analytics = base / "analytics"
    markov_analytics = analytics / "markov"

    for d in (features, raw, markov_analytics):
        d.mkdir(parents=True, exist_ok=True)

    # Some code may derive paths from an env var—offer a hint but keep monkeypatching hard refs.
    monkeypatch.setenv("MIE_DATA_DIR", str(base))

    # Patch modules that hold path constants
    # Features
    try:
        print("Patching mie_lib.features.build_features")
        import mie_lib.features.build_features as bf
        print("mie_lib.features.build_features imported")

        bf.FEATURES_DIR = features
        # RAW_DIR may exist in build_features; patch if present
        if hasattr(bf, "RAW_DIR"):
            bf.RAW_DIR = raw
        print("Patched mie_lib.features.build_features")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.features.build_features: {e}")
        pass

    # Markov engine (builders that load features)
    try:
        print("Patching mie_lib.analytics.markov.markov_engine")
        import mie_lib.analytics.markov.markov_engine as me
        print("mie_lib.analytics.markov.markov_engine imported")

        me.FEATURES_DIR = features
        print("Patched mie_lib.analytics.markov.markov_engine")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.analytics.markov.markov_engine: {e}")
        pass

    # HMM engine (loads features)
    try:
        print("Patching mie_lib.analytics.hmm.hmm_engine")
        import mie_lib.analytics.hmm.hmm_engine as he
        print("mie_lib.analytics.hmm.hmm_engine imported")

        he.FEATURES_DIR = features
        print("Patched mie_lib.analytics.hmm.hmm_engine")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.analytics.hmm.hmm_engine: {e}")
        pass

    # States model (where matrices & states are cached under analytics/markov)
    try:
        print("Patching mie_lib.analytics.markov.states_model")
        import mie_lib.analytics.markov.states_model as sm
        print("mie_lib.analytics.markov.states_model imported")

        sm.AN_MKV_DIR = markov_analytics
        # If states_model uses FEATURES_DIR internally, patch as well if present
        if hasattr(sm, "FEATURES_DIR"):
            sm.FEATURES_DIR = features
        print("Patched mie_lib.analytics.markov.states_model")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.analytics.markov.states_model: {e}")
        pass

    # Optionally patch any page helpers that directly read FEATURES_DIR if they import it
    try:
        # Pages are not part of the library, so we don't patch them here.
        # Tests for pages should handle mocking paths if needed.
        pass
    except (ImportError, AttributeError):
        pass

    # Patch test modules that import FEATURES_DIR at module scope
    print("Patching test modules")
    for test_mod in ("tests.test_features", "tests.test_markov", "tests.test_timezone"):
        try:
            print(f"Patching {test_mod}")
            tm = importlib.import_module(test_mod)
            if hasattr(tm, "FEATURES_DIR"):
                setattr(tm, "FEATURES_DIR", features)
            print(f"Patched {test_mod}")
        except (ImportError, AttributeError) as e:
            print(f"Failed to patch {test_mod}: {e}")
            pass
    print("Finished patching test modules")

    # --- Only chdir for tests that explicitly assert CWD-based data paths ---
    try:
        test_file = Path(str(request.fspath)).name
        if test_file == "test_features_update.py":
            monkeypatch.chdir(tmp_path)
            # Create 'data' symlink inside tmp CWD for relative data paths
            data_target = base
            data_link = Path.cwd() / "data"
            if not data_link.exists():
                try:
                    data_link.symlink_to(data_target, target_is_directory=True)
                except Exception:
                    data_link.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    print("_patch_data_roots finished")
    yield


@pytest.fixture
def features_tmp_dirs(tmp_path, monkeypatch):
    """
    Legacy fixture expected by tests/test_features.py.
    Returns a dict of the tmp data paths and ensures module constants
    point there (duplicated setup so tests can rely on it explicitly).
    """
    base = tmp_path / "data"
    features = base / "features"
    raw = base / "raw"
    analytics = base / "analytics"
    markov_analytics = analytics / "markov"

    for d in (features, raw, markov_analytics):
        d.mkdir(parents=True, exist_ok=True)

    # Patch the same constants
    try:
        print("Patching mie_lib.features.build_features in features_tmp_dirs")
        import mie_lib.features.build_features as bf

        bf.FEATURES_DIR = features
        if hasattr(bf, "RAW_DIR"):
            bf.RAW_DIR = raw
        print("Patched mie_lib.features.build_features in features_tmp_dirs")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.features.build_features in features_tmp_dirs: {e}")
        pass

    try:
        print("Patching mie_lib.analytics.markov.markov_engine in features_tmp_dirs")
        import mie_lib.analytics.markov.markov_engine as me

        me.FEATURES_DIR = features
        print("Patched mie_lib.analytics.markov.markov_engine in features_tmp_dirs")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.analytics.markov.markov_engine in features_tmp_dirs: {e}")
        pass

    try:
        print("Patching mie_lib.analytics.hmm.hmm_engine in features_tmp_dirs")
        import mie_lib.analytics.hmm.hmm_engine as he

        he.FEATURES_DIR = features
        print("Patched mie_lib.analytics.hmm.hmm_engine in features_tmp_dirs")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.analytics.hmm.hmm_engine in features_tmp_dirs: {e}")
        pass

    try:
        print("Patching mie_lib.analytics.markov.states_model in features_tmp_dirs")
        import mie_lib.analytics.markov.states_model as sm

        sm.AN_MKV_DIR = markov_analytics
        if hasattr(sm, "FEATURES_DIR"):
            sm.FEATURES_DIR = features
        print("Patched mie_lib.analytics.markov.states_model in features_tmp_dirs")
    except (ImportError, AttributeError) as e:
        print(f"Failed to patch mie_lib.analytics.markov.states_model in features_tmp_dirs: {e}")
        pass

    # Patch test modules that import FEATURES_DIR at module scope
    print("Patching test modules in features_tmp_dirs")
    for test_mod in ("tests.test_features", "tests.test_markov", "tests.test_timezone"):
        try:
            print(f"Patching {test_mod} in features_tmp_dirs")
            tm = importlib.import_module(test_mod)
            if hasattr(tm, "FEATURES_DIR"):
                setattr(tm, "FEATURES_DIR", features)
            print(f"Patched {test_mod} in features_tmp_dirs")
        except Exception as e:
            print(f"Failed to patch {test_mod} in features_tmp_dirs: {e}")
            pass
    print("Finished patching test modules in features_tmp_dirs")

    return {
        "data": base,
        "features": features,
        "raw": raw,
        "analytics": analytics,
        "markov": markov_analytics,
    }
