from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mie_lib.cli.markov_snapshots import (
    SNAPSHOT_METADATA_FILENAME,
    build_markov_snapshots,
)


@pytest.fixture
def markov_snapshot_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    markov_dir = data_dir / "analytics" / "markov"
    snapshot_root = data_dir / "analytics_snapshots" / "markov"
    tmp_root = data_dir / "tmp" / "markov_snapshot_build"
    for path in (markov_dir, snapshot_root, tmp_root):
        path.mkdir(parents=True, exist_ok=True)
    import mie_lib.cli.markov_snapshots as module

    monkeypatch.setattr(module, "DATA_DIR", data_dir)
    monkeypatch.setattr(module, "MARKOV_DIR", markov_dir)
    monkeypatch.setattr(module, "DEFAULT_DESTINATION_ROOT", snapshot_root)
    monkeypatch.setattr(module, "DEFAULT_TMP_ROOT", tmp_root)
    return SimpleNamespace(
        data_dir=data_dir,
        markov_dir=markov_dir,
        snapshot_root=snapshot_root,
        tmp_root=tmp_root,
    )


def _seed_markov_tree(root: Path, ticker: str, *, include_50y: bool) -> None:
    base = root / ticker
    matrix_dir = base / "matrices" / "binary" / "thr10" / "order1"
    matrix_dir.mkdir(parents=True, exist_ok=True)
    for win in ("1Y", "2Y", "5Y", "MAX"):
        (matrix_dir / f"{win}.parquet").write_text(win)
    if include_50y:
        (matrix_dir / "50Y.parquet").write_text("50Y")
    (matrix_dir / "matrix_metadata.json").write_text("{}")
    (base / "states.parquet").write_text("states")


def test_markov_snapshot_tracks_windows(markov_snapshot_env):
    _seed_markov_tree(markov_snapshot_env.markov_dir, "SPY", include_50y=True)
    _seed_markov_tree(markov_snapshot_env.markov_dir, "QQQ", include_50y=False)

    summary = build_markov_snapshots(
        ["SPY", "QQQ"],
        source_root=markov_snapshot_env.markov_dir,
        destination_root=markov_snapshot_env.snapshot_root,
        tmp_root=markov_snapshot_env.tmp_root,
    )

    entries = {entry["ticker"]: entry for entry in summary["entries"]}
    assert "50Y" in summary["windows_requested"]

    spy_dir = markov_snapshot_env.snapshot_root / "SPY" / "matrices" / "binary" / "thr10" / "order1"
    assert (spy_dir / "50Y.parquet").exists()
    assert "50Y" in entries["SPY"]["windows_found"]
    assert "50Y" not in entries["SPY"]["windows_missing"]

    assert "50Y" in entries["QQQ"]["windows_missing"]

    metadata_path = markov_snapshot_env.snapshot_root / SNAPSHOT_METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    assert metadata["copied_count"] == 2


def test_markov_snapshot_allow_missing(markov_snapshot_env):
    with pytest.raises(FileNotFoundError):
        build_markov_snapshots(
            ["MISSING"],
            source_root=markov_snapshot_env.markov_dir,
            destination_root=markov_snapshot_env.snapshot_root,
            tmp_root=markov_snapshot_env.tmp_root,
        )

    summary = build_markov_snapshots(
        ["MISSING"],
        source_root=markov_snapshot_env.markov_dir,
        destination_root=markov_snapshot_env.snapshot_root,
        tmp_root=markov_snapshot_env.tmp_root,
        allow_missing=True,
    )
    assert summary["copied_count"] == 0
    assert summary["missing"][0]["ticker"] == "MISSING"

    metadata_path = markov_snapshot_env.snapshot_root / SNAPSHOT_METADATA_FILENAME
    assert json.loads(metadata_path.read_text())["missing"]
