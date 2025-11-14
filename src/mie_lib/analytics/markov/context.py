"""Context selection compatibility shim.

Legacy pages import `select_context_row` from here. We delegate to the
stable shim in `aggregation` to avoid duplicating logic.
"""
from __future__ import annotations

from typing import Tuple, Optional
import pandas as pd

from .aggregation import select_context_row as _select


def select_context_row(df: pd.DataFrame, recent_sequence) -> Tuple[Optional[pd.Series], Optional[str]]:
    """Return (row_series, used_label) for a provided context.

    `recent_sequence` can be either a compact string like "GRN" or a list of
    raw state codes (e.g., ["U","N","D"]). If a list is provided, we
    convert it into a compact string by mapping U->G, N->N, D->R.
    """
    # Normalize input to compact string if a sequence list is given
    ctx = recent_sequence
    if isinstance(recent_sequence, (list, tuple)):
        # map raw->display compact
        mp = {"U": "G", "N": "N", "D": "R"}
        try:
            ctx = "".join(mp.get(str(x).upper(), str(x).upper()[:1]) for x in recent_sequence)
        except Exception:
            ctx = ""  # fallback
    return _select(df, ctx)


__all__ = ["select_context_row"]

