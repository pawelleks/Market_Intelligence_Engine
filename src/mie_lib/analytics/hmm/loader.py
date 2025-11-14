"""Compatibility shim for legacy HMM loader imports.

Forward to functions available in hmm_engine without changing semantics.
"""
from __future__ import annotations

from .hmm_engine import (
    HMMConfig,
    build_hmm_for_ticker,
    build_hmm_standardized_for_ticker,
)

__all__ = [
    "HMMConfig",
    "build_hmm_for_ticker",
    "build_hmm_standardized_for_ticker",
]

