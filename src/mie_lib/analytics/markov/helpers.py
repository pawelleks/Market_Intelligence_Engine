"""Helper shims for Markov analytics used by pages.

This module intentionally re-exports stable helper functions from the
`aggregation` shim so legacy imports like
`from mie_lib.analytics.markov.helpers import compute_multi_horizon_probs`
continue to work without altering underlying math.
"""
from __future__ import annotations

from .aggregation import (
    aggregate_to_state_matrix,
    compute_multi_horizon_probs,
    select_context_row,
)

__all__ = [
    "aggregate_to_state_matrix",
    "compute_multi_horizon_probs",
    "select_context_row",
]

