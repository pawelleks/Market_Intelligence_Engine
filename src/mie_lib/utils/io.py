from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

# -----------------------------------------------------------------
# Atomic Write Helpers (Ensures File Integrity)
# -----------------------------------------------------------------

def _ensure_dir_flush(path: Path):
    """Creates parent directory if needed and tries to flush data to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # On Unix-like systems, flushing the directory guarantees the file name exists
        dfd = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except Exception:
        pass


def atomic_write_parquet(df: pd.DataFrame, path: Path):
    """Writes DataFrame to Parquet atomically (temp file rename)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    
    _ensure_dir_flush(path)
    
    df.to_parquet(tmp, index=False)
    
    try:
        os.replace(tmp, path)
        _ensure_dir_flush(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def atomic_write_json(obj: dict[str, Any], path: Path):
    """Writes Python dict to JSON atomically (temp file rename)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    
    _ensure_dir_flush(path)
    
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    
    try:
        os.replace(tmp, path)
        _ensure_dir_flush(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass