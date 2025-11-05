"""
I/O helpers for reading/writing datasets.
Lightweight stubs: actual implementations should import pandas inside functions to avoid heavy imports at module import time.
"""
from pathlib import Path


def read_parquet(path):
    """Read a parquet file into a pandas DataFrame.
    This imports pandas lazily so importing this module doesn't require pandas to be installed.
    """
    try:
        import pandas as pd
    except Exception as e:
        raise RuntimeError("pandas is required to read parquet files") from e
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")
    return pd.read_parquet(p)


def write_parquet(df, path, **kwargs):
    """Write DataFrame to parquet.
    Creates parent directories as needed.
    """
    try:
        import pandas as pd
    except Exception as e:
        raise RuntimeError("pandas is required to write parquet files") from e
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, **kwargs)

