from __future__ import annotations

from types import SimpleNamespace

import pytest


def _ensure_dirs(*paths):
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def expected_moves_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw"
    options_dir = data_dir / "analytics" / "options"
    meta_dir = data_dir / "meta"
    raw_options_dir = raw_dir / "options"
    _ensure_dirs(raw_dir, options_dir, meta_dir, raw_options_dir)

    from mie_lib.utils import paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths_mod, "RAW_DIR", raw_dir)
    monkeypatch.setattr(paths_mod, "OPTIONS_DIR", options_dir)
    monkeypatch.setattr(paths_mod, "META_DIR", meta_dir)

    import mie_lib.options.expected_move as expected_move_module

    monkeypatch.setattr(expected_move_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(expected_move_module, "RAW_DIR", raw_dir)
    monkeypatch.setattr(expected_move_module, "RAW_OPTIONS_DIR", raw_options_dir)

    return SimpleNamespace(
        data_dir=data_dir,
        raw_dir=raw_dir,
        raw_options_dir=raw_options_dir,
        options_dir=options_dir,
        meta_dir=meta_dir,
        module=expected_move_module,
    )
