"""State code conversions compatibility shim.

Legacy pages import `to_compact`/`to_verbose`. Provide simple mappings.
- Raw codes used in analytics: U (Up/Green), N (Neutral), D (Down/Red)
- Compact UI codes: G, N, R
- Verbose string codes: 'U-N-D' style with hyphens
"""
from __future__ import annotations

from typing import Iterable, List

_RAW_TO_COMPACT = {"U": "G", "N": "N", "D": "R"}
_COMPACT_TO_RAW = {v: k for k, v in _RAW_TO_COMPACT.items()}


def to_compact(context: str) -> str:
    """Map raw context like 'U-N-D' or 'UND' to compact 'GNR'."""
    if not context:
        return ""
    s = str(context).replace("-", "").upper()
    return "".join(_RAW_TO_COMPACT.get(ch, ch) for ch in s)


def to_verbose(context: str) -> str:
    """Map compact 'GNR' or raw 'UND' to verbose 'U-N-D'."""
    if not context:
        return ""
    s = str(context).replace("-", "").upper()
    # If provided in compact, expand to raw first
    raw_chars: List[str] = []
    for ch in s:
        if ch in _COMPACT_TO_RAW:
            raw_chars.append(_COMPACT_TO_RAW[ch])
        else:
            raw_chars.append(ch)
    return "-".join(raw_chars)


__all__ = ["to_compact", "to_verbose"]

