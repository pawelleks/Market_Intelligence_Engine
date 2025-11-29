from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from mie_lib.cli.hmm_snapshots import (
    SNAPSHOT_METADATA_FILENAME,
    build_hmm_snapshots,
)


@pytest.fixture
def hmm_snapshot_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    hmm_dir = data_dir / "analytics" / "hmm"
    snapshot_root = data_dir / "analytics_snapshots" / "hmm"
    tmp_root = data_dir / "tmp" / "hmm_snapshot_build"

    for path in (hmm_dir, snapshot_root, tmp_root):
        path.mkdir(parents=True, exist_ok=True)

    from mie_lib.utils import paths as paths_mod
    import mie_lib.cli.hmm_snapshots as snapshots_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths_mod, "HMM_DIR", hmm_dir)

    monkeypatch.setattr(snapshots_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(snapshots_mod, "HMM_DIR", hmm_dir)
    monkeypatch.setattr(snapshots_mod, "DEFAULT_DESTINATION_ROOT", snapshot_root)
    monkeypatch.setattr(snapshots_mod, "DEFAULT_TMP_ROOT", tmp_root)

    return SimpleNamespace(
        data_dir=data_dir,
        hmm_dir=hmm_dir,
        snapshot_root=snapshot_root,
        tmp_root=tmp_root,
    )


def test_hmm_snapshot_builder_copies_full_tree(hmm_snapshot_env):
    ticker_dir = hmm_snapshot_env.hmm_dir / "SPY"
    ticker_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-02"]), "value": [1.0]})
    df.to_parquet(ticker_dir / "hmm_probs.parquet", index=False)
    df.to_parquet(ticker_dir / "hmm_states.parquet", index=False)
    df.to_parquet(ticker_dir / "hmm_metrics.parquet", index=False)
    (ticker_dir / "hmm_metadata.json").write_text(json.dumps({"ticker": "SPY"}))

    summary = build_hmm_snapshots(
        tickers=["SPY"],
        destination_root=hmm_snapshot_env.snapshot_root,
        tmp_root=hmm_snapshot_env.tmp_root,
        allow_missing=False,
    )

    dest_dir = hmm_snapshot_env.snapshot_root / "SPY"
    for filename in (
        "hmm_probs.parquet",
        "hmm_states.parquet",
        "hmm_metrics.parquet",
        "hmm_metadata.json",
    ):
        assert (dest_dir / filename).exists()

    metadata_path = hmm_snapshot_env.snapshot_root / SNAPSHOT_METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    assert metadata["tickers_requested"] == ["SPY"]
    assert metadata["tickers_succeeded"] == ["SPY"]
    assert metadata["tickers_missing"] == {}
    assert metadata["files_copied"]["SPY"], "Expected files_copied entry"
    assert summary["tickers_succeeded"] == ["SPY"]


def test_hmm_snapshot_builder_allow_missing_behavior(hmm_snapshot_env):
    summary = build_hmm_snapshots(
        tickers=["QQQ"],
        destination_root=hmm_snapshot_env.snapshot_root,
        tmp_root=hmm_snapshot_env.tmp_root,
        allow_missing=True,
    )

    metadata_path = hmm_snapshot_env.snapshot_root / SNAPSHOT_METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text())
    assert metadata["tickers_succeeded"] == []
    assert "QQQ" in metadata["tickers_missing"]
    assert summary["tickers_missing"] == metadata["tickers_missing"]

    with pytest.raises(FileNotFoundError):
        build_hmm_snapshots(
            tickers=["MISSING"],
            destination_root=hmm_snapshot_env.snapshot_root,
            tmp_root=hmm_snapshot_env.tmp_root,
            allow_missing=False,
        )
