from __future__ import annotations
import importlib as _il
_mod = _il.import_module("app.pages.02_Regime_Research_Lab")
for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

