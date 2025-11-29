from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from mie_lib.utils.paths import DATA_DIR, OPTIONS_DIR

LOG = logging.getLogger(__name__)

SNAPSHOT_METADATA_FILENAME = "SNAPSHOT_METADATA.json"
DEFAULT_DESTINATION_ROOT = DATA_DIR / "analytics_snapshots" / "options"
DEFAULT_TMP_ROOT = DATA_DIR / "tmp" / "options_snapshots"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _expected_source_files(
    ticker: str,
    source_root: Path,
    expect_weekly_reference: bool,
) -> list[tuple[Path, bool]]:
    slug = ticker.lower()
    entries: list[tuple[Path, bool]] = [
        (source_root / f"{slug}_expected_moves.parquet", True),
    ]
    weekly_path = source_root / f"{slug}_weekly_reference.parquet"
    if weekly_path.exists() or expect_weekly_reference:
        entries.append((weekly_path, bool(expect_weekly_reference)))
    return entries


def _write_metadata(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(path)


def _copy_files_to_stage(files: Iterable[Path], stage_dir: Path) -> list[str]:
    copied: list[str] = []
    for src in files:
        dest = stage_dir / src.name
        shutil.copy2(src, dest)
        copied.append(src.name)
    return copied


def _prepare_stage_dir(tmp_root: Path, ticker: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    stage_dir = tmp_root / f"{ticker.upper()}_{ts}"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def _build_metadata(
    *,
    ticker: str,
    destination_root: Path,
    snapshot_dir: Path,
    source_root: Path,
    files_copied: list[str],
    missing_files: list[str],
    allow_missing: bool,
    expect_weekly_reference: bool,
    status: str,
    skip_reason: str | None,
) -> dict:
    metadata = {
        "generated_timestamp": _timestamp(),
        "ticker": ticker,
        "tickers_included": [ticker],
        "source_root": str(source_root),
        "destination_root": str(destination_root),
        "snapshot_path": str(snapshot_dir),
        "files_copied": sorted(files_copied),
        "missing_files": sorted(missing_files),
        "allow_missing": allow_missing,
        "expect_weekly_reference": expect_weekly_reference,
        "status": status,
    }
    if skip_reason:
        metadata["skip_reason"] = skip_reason
    return metadata


def build_expected_moves_snapshots(
    tickers: Sequence[str],
    *,
    source_root: Path | None = None,
    destination_root: Path | None = None,
    tmp_root: Path | None = None,
    allow_missing: bool = False,
    expect_weekly_reference: bool = True,
) -> list[dict]:
    if not tickers:
        raise ValueError("Expected at least one ticker to snapshot")

    resolved_tickers = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not resolved_tickers:
        raise ValueError("No valid tickers resolved for snapshots")

    source = Path(source_root) if source_root else OPTIONS_DIR
    destination = Path(destination_root) if destination_root else DEFAULT_DESTINATION_ROOT
    tmp_base = Path(tmp_root) if tmp_root else DEFAULT_TMP_ROOT

    _ensure_dir(destination)
    _ensure_dir(tmp_base)

    results: list[dict] = []
    for ticker in resolved_tickers:
        snapshot_dir = destination / ticker
        expected_files = _expected_source_files(ticker, source, expect_weekly_reference)
        existing_files = [path for path, _ in expected_files if path.exists()]
        missing_required = [path.name for path, required in expected_files if required and not path.exists()]
        missing_optional = [path.name for path, required in expected_files if not required and not path.exists()]
        missing_all = missing_required + missing_optional

        if missing_required and not allow_missing:
            raise FileNotFoundError(
                f"Missing required expected-moves files for {ticker}: {', '.join(missing_required)}"
            )

        if missing_required and allow_missing:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            metadata = _build_metadata(
                ticker=ticker,
                destination_root=destination,
                snapshot_dir=snapshot_dir,
                source_root=source,
                files_copied=[],
                missing_files=missing_all,
                allow_missing=allow_missing,
                expect_weekly_reference=expect_weekly_reference,
                status="skipped",
                skip_reason="required_files_missing",
            )
            _write_metadata(snapshot_dir / SNAPSHOT_METADATA_FILENAME, metadata)
            LOG.warning(
                "expected-moves snapshot skipped ticker=%s missing=%s", ticker, ",".join(missing_required)
            )
            results.append(metadata)
            continue

        if not existing_files:
            LOG.warning("expected-moves snapshot found no source files for ticker=%s", ticker)
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            metadata = _build_metadata(
                ticker=ticker,
                destination_root=destination,
                snapshot_dir=snapshot_dir,
                source_root=source,
                files_copied=[],
                missing_files=missing_all,
                allow_missing=allow_missing,
                expect_weekly_reference=expect_weekly_reference,
                status="skipped",
                skip_reason="no_source_files",
            )
            _write_metadata(snapshot_dir / SNAPSHOT_METADATA_FILENAME, metadata)
            results.append(metadata)
            continue

        stage_dir = _prepare_stage_dir(tmp_base, ticker)
        try:
            copied_files = _copy_files_to_stage(existing_files, stage_dir)
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir)
            shutil.move(str(stage_dir), str(snapshot_dir))
        finally:
            if stage_dir.exists():
                shutil.rmtree(stage_dir, ignore_errors=True)

        status = "ok" if not missing_optional else "partial"
        metadata = _build_metadata(
            ticker=ticker,
            destination_root=destination,
            snapshot_dir=snapshot_dir,
            source_root=source,
            files_copied=copied_files,
            missing_files=missing_all,
            allow_missing=allow_missing,
            expect_weekly_reference=expect_weekly_reference,
            status=status,
            skip_reason=None,
        )
        _write_metadata(snapshot_dir / SNAPSHOT_METADATA_FILENAME, metadata)
        LOG.info(
            "expected-moves snapshot complete ticker=%s files=%s status=%s",
            ticker,
            ",".join(copied_files),
            status,
        )
        results.append(metadata)

    return results


__all__ = [
    "build_expected_moves_snapshots",
    "SNAPSHOT_METADATA_FILENAME",
    "DEFAULT_DESTINATION_ROOT",
    "DEFAULT_TMP_ROOT",
]
