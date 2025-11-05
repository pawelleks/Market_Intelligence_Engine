from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_root_on_path():
    """Ensure the project root (parent of 'app') is on sys.path exactly once.
    Safe: no side-effects besides sys.path; returns True if modified, False otherwise.
    """
    this_file = Path(__file__).resolve()
    app_dir = this_file.parent
    root = app_dir.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
        return True
    return False

