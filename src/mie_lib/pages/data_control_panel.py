from __future__ import annotations
import importlib as _il
_mod = _il.import_module("app.pages.04_Data_Control_Panel")
for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

