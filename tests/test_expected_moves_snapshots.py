from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from mie_lib.cli.expected_moves_snapshots import (
    SNAPSHOT_METADATA_FILENAME,
    build_expected_moves_snapshots,
)


@pytest.fixture
def snapshot_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    options_dir = data_dir / "analytics" / "options"
    meta_dir = data_dir / "meta"
    tmp_root = data_dir / "tmp" / "options_snapshots"
    snapshot_root = data_dir / "analytics_snapshots" / "options"

    for path in (options_dir, meta_dir, tmp_root, snapshot_root):
        path.mkdir(parents=True, exist_ok=True)

    from mie_lib.utils import paths as paths_mod
    import mie_lib.cli.expected_moves_snapshots as snapshots_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths_mod, "OPTIONS_DIR", options_dir)
    monkeypatch.setattr(paths_mod, "META_DIR", meta_dir)

    monkeypatch.setattr(snapshots_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(snapshots_mod, "OPTIONS_DIR", options_dir)
    monkeypatch.setattr(snapshots_mod, "DEFAULT_DESTINATION_ROOT", snapshot_root)
    monkeypatch.setattr(snapshots_mod, "DEFAULT_TMP_ROOT", tmp_root)

    return SimpleNamespace(
        data_dir=data_dir,
        options_dir=options_dir,
        snapshot_root=snapshot_root,
        tmp_root=tmp_root,
    )


def test_snapshot_builder_copies_expected_files(snapshot_env):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "expected_move_pct": [0.02],
        }
    )
    expected_moves_path = snapshot_env.options_dir / "spy_expected_moves.parquet"
    weekly_path = snapshot_env.options_dir / "spy_weekly_reference.parquet"
    df.to_parquet(expected_moves_path, index=False)
    df.to_parquet(weekly_path, index=False)

    results = build_expected_moves_snapshots(
        tickers=["SPY"],
        destination_root=snapshot_env.snapshot_root,
        tmp_root=snapshot_env.tmp_root,
        allow_missing=False,
        expect_weekly_reference=True,
    )

    snapshot_dir = snapshot_env.snapshot_root / "SPY"
    assert (snapshot_dir / "spy_expected_moves.parquet").exists()
    assert (snapshot_dir / "spy_weekly_reference.parquet").exists()

    metadata_path = snapshot_dir / SNAPSHOT_METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    assert metadata["status"] == "ok"
    assert metadata["files_copied"] == [
        "spy_expected_moves.parquet",
        "spy_weekly_reference.parquet",
    ]
    assert metadata["missing_files"] == []
    assert results and results[0]["status"] == "ok"


def test_snapshot_builder_allow_missing_records_skip(snapshot_env):
    results = build_expected_moves_snapshots(
        tickers=["SPY"],
        destination_root=snapshot_env.snapshot_root,
        tmp_root=snapshot_env.tmp_root,
        allow_missing=True,
        expect_weekly_reference=True,
    )

    snapshot_dir = snapshot_env.snapshot_root / "SPY"
    metadata_path = snapshot_dir / SNAPSHOT_METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    assert metadata["status"] == "skipped"
    assert metadata.get("skip_reason") == "required_files_missing"
    assert "spy_expected_moves.parquet" in metadata["missing_files"]
    assert results[0]["status"] == "skipped"
