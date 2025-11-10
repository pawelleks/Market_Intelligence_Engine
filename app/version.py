"""Application version helper.
Reads latest git tag if available, falls back to hardcoded version.
Import-safe (no Streamlit dependency).
"""
from __future__ import annotations
import subprocess

__version__ = "v0.9.0-markov-fix"

def get_version() -> str:
    """Attempt to read the latest annotated or lightweight tag.
    Falls back to __version__ on any failure.
    """
    try:
        out = subprocess.check_output([
            "git", "describe", "--tags", "--abbrev=0"
        ], stderr=subprocess.DEVNULL, timeout=1).decode().strip()
        if out:
            return out
    except Exception:
        pass
    return __version__

__all__ = ["get_version", "__version__"]

