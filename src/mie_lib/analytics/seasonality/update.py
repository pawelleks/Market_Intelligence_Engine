from __future__ import annotations
from pathlib import Path
import pandas as pd
from .build_facts import build_facts_for_ticker, load_seasonality_config

SEAS_BASE_DIR = Path("data")/"seasonality"/"base"


def update_seasonality(tickers: list[str], since: str | None = None, dry_run: bool=False):
    """Rebuild facts for provided tickers. If `since` provided, this function
    can be extended to read partial updates; currently it rebuilds full for simplicity
    per offline batch philosophy (deterministic).
    """
    cfg = load_seasonality_config()
    horizons = cfg.get("LOOKBACK_WINDOWS", [5,10,20,30,50,"ALL"])
    out = []
    for t in tickers:
        t = t.upper().strip()
        if not (SEAS_BASE_DIR / f"{t}.parquet").exists():
            # skip silently; caller can log
            continue
        paths = build_facts_for_ticker(t, horizons=horizons, dry_run=dry_run)
        out.extend(paths)
    return out

