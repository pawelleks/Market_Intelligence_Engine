from __future__ import annotations

import importlib


def test_public_api_imports_core():
    # Base package
    mie = importlib.import_module("mie_lib")
    assert mie is not None

    # Markov package and engine
    mk = importlib.import_module("mie_lib.analytics.markov")
    mke = importlib.import_module("mie_lib.analytics.markov.markov_engine")
    assert hasattr(mk, "MarkovConfig"), "MarkovConfig must be exported from mie_lib.analytics.markov"
    assert hasattr(mk, "build_markov_for_ticker"), "build_markov_for_ticker must be exported from mie_lib.analytics.markov"
    # Engine must expose MarkovConfig and builder as well
    assert hasattr(mke, "MarkovConfig") and hasattr(mke, "build_markov_for_ticker")

    # Aggregation shim
    agg = importlib.import_module("mie_lib.analytics.markov.aggregation")
    for fn in ("aggregate_to_state_matrix", "select_context_row", "compute_multi_horizon_probs"):
        assert hasattr(agg, fn), f"Aggregation shim must expose {fn}"

    # Canonical paths
    paths = importlib.import_module("mie_lib.utils.paths")
    for name in ("ROOT", "DATA_DIR", "RAW_DIR", "FEATURES_DIR", "MARKOV_DIR", "HMM_DIR", "SEASONALITY_DIR"):
        assert hasattr(paths, name), f"paths must expose {name}"
    for fn in (
        "features_parquet_path",
        "markov_out_dir",
        "markov_states_path",
        "markov_counts_path",
        "markov_matrix_path_flat",
        "markov_predictions_path",
        "markov_metadata_path",
        "markov_matrix_grid_path",
        "markov_matrix_grid_meta_dir",
        "hmm_out_dir",
        "hmm_std_out_dir",
        "seasonality_base_path",
    ):
        assert hasattr(paths, fn), f"paths must expose {fn}"


def test_public_api_imports_shims():
    # HMM shim loader
    hmm_loader = importlib.import_module("mie_lib.analytics.hmm.loader")
    assert hasattr(hmm_loader, "HMMConfig")
    assert hasattr(hmm_loader, "build_hmm_for_ticker")

    # Seasonality shim loader should import without errors and expose base builder
    seas_loader = importlib.import_module("mie_lib.analytics.seasonality.loader")
    assert seas_loader is not None
    # Optional symbol presence (do not fail hard if absent, but prefer it exists)
    assert hasattr(seas_loader, "build_seasonality_base_for_ticker"), (
        "seasonality.loader should expose build_seasonality_base_for_ticker via re-export"
    )

