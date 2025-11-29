from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Sequence

from mie_lib.utils.paths import DATA_DIR, HMM_DIR

LOG = logging.getLogger(__name__)

SNAPSHOT_METADATA_FILENAME = "SNAPSHOT_METADATA.json"
DEFAULT_DESTINATION_ROOT = DATA_DIR / "analytics_snapshots" / "hmm"
DEFAULT_TMP_ROOT = DATA_DIR / "tmp" / "hmm_snapshot_build"
REQUIRED_PATTERNS = (
    "hmm_probs.parquet",
    "hmm_states.parquet",
    "hmm_metrics.parquet",
    "hmm_metadata.json",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write_json(path: Path, payload: Dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(path)


def _prepare_stage_dir(tmp_root: Path, ticker: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    stage_dir = tmp_root / f"{ticker.upper()}_{ts}"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def _collect_required_files(source_dir: Path) -> tuple[dict[str, list[str]], list[str]]:
    found: dict[str, list[str]] = {}
    for pattern in REQUIRED_PATTERNS:
        matches = list(source_dir.rglob(pattern))
        if matches:
            found[pattern] = [str(p) for p in matches]
    missing = [p for p in REQUIRED_PATTERNS if p not in found]
    return found, missing


def _list_files_relative(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def build_hmm_snapshots(
    tickers: Sequence[str],
    *,
    source_root: Path | None = None,
    destination_root: Path | None = None,
    tmp_root: Path | None = None,
    allow_missing: bool = False,
) -> dict:
    if not tickers:
        raise ValueError("build_hmm_snapshots requires at least one ticker")

    resolved = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not resolved:
        raise ValueError("No valid HMM tickers resolved")

    source = Path(source_root) if source_root else HMM_DIR
    destination = Path(destination_root) if destination_root else DEFAULT_DESTINATION_ROOT
    tmp_base = Path(tmp_root) if tmp_root else DEFAULT_TMP_ROOT

    _ensure_dir(destination)
    _ensure_dir(tmp_base)

    generated_at = _timestamp()
    tickers_missing: dict[str, list[str]] = {}
    files_copied: dict[str, list[str]] = {}
    succeeded: list[str] = []

    for ticker in resolved:
        src_dir = source / ticker
        if not src_dir.exists() or not src_dir.is_dir():
            missing_info = ["source_dir_missing"]
            if not allow_missing:
                raise FileNotFoundError(f"HMM analytics missing for {ticker}: {src_dir}")
            tickers_missing[ticker] = missing_info
            LOG.warning("hmm snapshot skip ticker=%s reason=source_dir_missing", ticker)
            continue

        required_map, missing_patterns = _collect_required_files(src_dir)
        if missing_patterns and not allow_missing:
            raise FileNotFoundError(
                f"Missing required HMM files for {ticker}: {', '.join(missing_patterns)}"
            )
        if missing_patterns:
            tickers_missing[ticker] = missing_patterns
            LOG.warning(
                "hmm snapshot missing optional files ticker=%s missing=%s",
                ticker,
                ",".join(missing_patterns),
            )
            continue

        stage_dir = _prepare_stage_dir(tmp_base, ticker)
        dest_dir = destination / ticker
        try:
            shutil.copytree(src_dir, stage_dir, dirs_exist_ok=True)
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.move(stage_dir, dest_dir)
        finally:
            if stage_dir.exists():
                shutil.rmtree(stage_dir, ignore_errors=True)

        files_copied[ticker] = _list_files_relative(dest_dir)
        succeeded.append(ticker)
        LOG.info(
            "hmm snapshot complete ticker=%s files=%s",
            ticker,
            len(files_copied[ticker]),
        )

    metadata = {
        "generated_at": generated_at,
        "tickers_requested": resolved,
        "tickers_succeeded": succeeded,
        "tickers_missing": tickers_missing,
        "allow_missing": allow_missing,
        "source_root": str(source),
        "destination_root": str(destination),
        "files_copied": files_copied,
    }

    _atomic_write_json(destination / SNAPSHOT_METADATA_FILENAME, metadata)
    return metadata


__all__ = [
    "build_hmm_snapshots",
    "SNAPSHOT_METADATA_FILENAME",
    "DEFAULT_DESTINATION_ROOT",
    "DEFAULT_TMP_ROOT",
]
