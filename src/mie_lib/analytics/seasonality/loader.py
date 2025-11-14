"""Compatibility shim for legacy seasonality loader imports.

This module intentionally provides minimal aliases to existing functionality
in this package to avoid breaking pages/tests that import
`mie_lib.analytics.seasonality.loader`.
"""
from __future__ import annotations

try:
    from .base_builder import *  # noqa: F401,F403
except Exception:
    pass
try:
    from .preprocess import *  # noqa: F401,F403
except Exception:
    pass

