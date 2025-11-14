# Public API for mie_lib.analytics.markov
from .markov_engine import (
    MarkovConfig,
    build_markov_for_ticker,
    build_markov_order_sweep,
    load_markov_matrix_grid,
    get_markov_features_alignment,
    load_features_for_markov,
)

# Re-export selected helpers from states_model for convenience
from .states_model import (
    build_states_from_features,
    states_for,
    derive_matrix,
    classify_tri_state,
    classify_binary_state,
)

# Optional: re-export helper shim module symbols if present
try:
    from .helpers import compute_multi_horizon_probs, select_context_row  # noqa: F401
except Exception:
    # helpers module may be added later; keep import-safe
    pass

# Optional: export aggregation shim helpers for legacy import paths
try:
    from .aggregation import aggregate_to_state_matrix, select_context_row, compute_multi_horizon_probs  # noqa: F401
except Exception:
    pass

# Explicit public surface
__all__ = [
    # markov_engine
    "MarkovConfig",
    "build_markov_for_ticker",
    "build_markov_order_sweep",
    "load_markov_matrix_grid",
    "get_markov_features_alignment",
    "load_features_for_markov",
    # states_model convenience exports
    "build_states_from_features",
    "states_for",
    "derive_matrix",
    "classify_tri_state",
    "classify_binary_state",
    # aggregation helpers
    "aggregate_to_state_matrix",
    "select_context_row",
    "compute_multi_horizon_probs",
]
