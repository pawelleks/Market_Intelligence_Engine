from __future__ import annotations
import importlib as _il
from pathlib import Path
import pandas as _pd

_mod = _il.import_module("app.pages.04_Hidden_Markov_Model")
for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

# Provide small helper expected by tests

def _safe_pick_context_row(df: _pd.DataFrame, ctx: str | None):
    if ctx is None or str(ctx).strip() == "":
        return df.iloc[0] if not df.empty else None
    m = df[df.get("context", _pd.Series(index=df.index, dtype=str)).astype(str) == str(ctx)]
    return (m.iloc[0] if not m.empty else (df.iloc[0] if not df.empty else None))
