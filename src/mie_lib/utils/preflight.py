from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA = Path("data")
FEAT_DIR = DATA / "features"
SEAS_BASE_DIR = DATA / "seasonality" / "base"
HMM_DIR = DATA / "analytics" / "hmm"


def ensure_parquet(path: Path, required_cols: list[str]) -> tuple[pd.DataFrame | None, list[str], str]:
    """Load a parquet and ensure required columns exist.
    Returns (df or None, missing_cols, err_str). Do not raise.
    Normalizes date columns to tz-naive if present.
    """
    missing: list[str] = []
    if path is None or not Path(path).exists():
        return None, required_cols.copy(), f"File not found: {path}"
    try:
        df = pd.read_parquet(path)
    except Exception as e:
        return None, required_cols.copy(), f"read_parquet failed: {e}"
    cols = set(df.columns)
    missing = [c for c in required_cols if c not in cols]
    # Normalize 'date' if present
    if 'date' in df.columns:
        try:
            df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert(None)
        except Exception:
            pass
    return df, missing, ""


def find_latest_feature(ticker: str) -> Path | None:
    p = FEAT_DIR / f"{ticker}.parquet"
    return p if p.exists() else None


def find_seasonality_base(ticker: str) -> Path | None:
    p = SEAS_BASE_DIR / f"{ticker}.parquet"
    return p if p.exists() else None


def find_hmm_artifacts(ticker: str) -> dict[str, Path | None]:
    base = HMM_DIR / ticker
    paths = {
        'probs': base / 'hmm_probs.parquet',
        'states': base / 'hmm_states.parquet',
        'metrics': base / 'hmm_metrics.parquet',
    }
    for k in list(paths):
        if not paths[k].exists():
            # try nested 5y/states2
            alt = base / 'win5y' / 'states2' / paths[k].name
            paths[k] = alt if alt.exists() else None
    return paths


def simple_cli_hint(kind: str, ticker: str) -> str:
    kind = (kind or '').lower()
    if kind == 'features':
        return "Run: python cli/mie.py build-features --mode full"
    if kind == 'seasonality':
        return f"Run: python cli/mie.py build-seasonality-base --ticker \"{ticker}\""
    if kind == 'hmm':
        return f"Run: python cli/mie.py build-hmm --ticker {ticker}"
    return "See cli/mie.py for available commands."
