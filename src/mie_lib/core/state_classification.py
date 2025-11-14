"""
Core state classification logic.
"""
from __future__ import annotations

from typing import Literal

TriLabel = Literal["Green", "Neutral", "Red"]


def classify_tri_state(return_value: float, threshold_bps: int) -> TriLabel:
    """Classify a single-period return into tri-state regime.

    Args:
        return_value: Return in decimal form, e.g. 0.001 for +0.10%.
        threshold_bps: Threshold in basis points (e.g. 10, 15, 20).

    Returns:
        "Green"   if return_value >= +T
        "Red"     if return_value <= -T
        "Neutral" if -T < return_value < +T

    Notes:
        T = threshold_bps * 0.0001
        Uses full numerical precision of return_value (no UI rounding).
        Thresholds are INCLUSIVE for Green/Red on the boundary.
    """
    try:
        r = float(return_value)
        T = float(int(threshold_bps)) / 10000.0
    except Exception:
        return "Neutral"
    if r >= T:
        return "Green"
    if r <= -T:
        return "Red"
    return "Neutral"

