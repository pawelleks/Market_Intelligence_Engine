from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from mie_lib.utils.paths import DATA_DIR, MARKOV_DIR

LOG = logging.getLogger(__name__)

SNAPSHOT_METADATA_FILENAME = "SNAPSHOT_METADATA.json"
DEFAULT_DESTINATION_ROOT = DATA_DIR / "analytics_snapshots" / "markov"
DEFAULT_TMP_ROOT = DATA_DIR / "tmp" / "markov_snapshot_build"
DEFAULT_WINDOWS = ("1Y", "2Y", "5Y", "10Y", "20Y", "50Y", "MAX")


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _prepare_run_dir(tmp_root: Path) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = tmp_root / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def _collect_windows(ticker_dir: Path, expected: set[str]) -> tuple[dict[str, list[str]], set[str]]:
    base = ticker_dir / "matrices"
    by_mode: dict[str, list[str]] = {}
    windows: set[str] = set()
    if not base.exists():
        return by_mode, windows
    for mode_dir in base.iterdir():
        if not mode_dir.is_dir():
            continue
        mode = mode_dir.name.lower()
        mode_windows: set[str] = set()
        for thr_dir in mode_dir.iterdir():
            if not thr_dir.is_dir():
                continue
            for order_dir in thr_dir.iterdir():
                if not order_dir.is_dir():
                    continue
                for file in order_dir.glob("*.parquet"):
                    key = file.stem.upper()
                    if key in expected:
                        mode_windows.add(key)
                        windows.add(key)
        if mode_windows:
            by_mode[mode] = sorted(mode_windows)
    return by_mode, windows


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(path)


def build_markov_snapshots(
    tickers: Sequence[str],
    *,
    source_root: Path | None = None,
    destination_root: Path | None = None,
    tmp_root: Path | None = None,
    allow_missing: bool = False,
    windows: Sequence[str] | None = None,
) -> dict:
    if not tickers:
        raise ValueError("build_markov_snapshots requires at least one ticker")

    resolved = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not resolved:
        raise ValueError("No valid Markov tickers resolved")

    source = Path(source_root) if source_root else MARKOV_DIR
    destination = Path(destination_root) if destination_root else DEFAULT_DESTINATION_ROOT
    tmp_base = Path(tmp_root) if tmp_root else DEFAULT_TMP_ROOT
    windows_cfg = [str(w).upper() for w in (windows or DEFAULT_WINDOWS) if str(w).strip()]
    if not windows_cfg:
        windows_cfg = list(DEFAULT_WINDOWS)
    expected_windows = set(windows_cfg)

    _ensure_dir(destination)
    _ensure_dir(tmp_base)

    run_dir = _prepare_run_dir(tmp_base)
    generated_at = _timestamp()
    entries: list[dict] = []
    missing: list[dict] = []

    for ticker in resolved:
        src_dir = source / ticker
        if not src_dir.exists() or not src_dir.is_dir():
            entry = {
                "ticker": ticker,
                "status": "missing_source",
                "source_path": str(src_dir),
            }
            if not allow_missing:
                shutil.rmtree(run_dir, ignore_errors=True)
                raise FileNotFoundError(f"Markov analytics missing for {ticker}: {src_dir}")
            missing.append(entry)
            entries.append(entry)
            LOG.warning("markov snapshot skip ticker=%s reason=source_dir_missing", ticker)
            continue

        stage_dir = run_dir / ticker
        dest_dir = destination / ticker
        stage_dir.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        try:
            shutil.copytree(src_dir, stage_dir, dirs_exist_ok=True)
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.move(stage_dir, dest_dir)
        finally:
            if stage_dir.exists():
                shutil.rmtree(stage_dir, ignore_errors=True)
        duration = time.perf_counter() - start
        if dest_dir.exists():
            file_count = _count_files(dest_dir)
            windows_by_mode, windows_found = _collect_windows(dest_dir, expected_windows)
        else:
            file_count = 0
            windows_by_mode, windows_found = {}, set()
        missing_windows = [w for w in windows_cfg if w not in windows_found]
        entry = {
            "ticker": ticker,
            "status": "success",
            "source_path": str(src_dir),
            "dest_path": str(dest_dir),
            "file_count": file_count,
            "duration_s": duration,
            "windows_found": sorted(windows_found),
            "windows_missing": missing_windows,
            "windows_by_mode": windows_by_mode,
        }
        entries.append(entry)
        if missing_windows:
            LOG.warning(
                "markov snapshot ticker=%s missing_windows=%s", ticker, ",".join(missing_windows)
            )
        else:
            LOG.info("markov snapshot complete ticker=%s files=%s", ticker, file_count)

    shutil.rmtree(run_dir, ignore_errors=True)

    metadata = {
        "generated_at": generated_at,
        "tickers": resolved,
        "copied_count": sum(1 for e in entries if e.get("status") == "success"),
        "missing": missing,
        "source_root": str(source),
        "snapshot_root": str(destination),
        "tmp_root": str(tmp_base),
        "windows_requested": windows_cfg,
        "entries": entries,
    }
    _atomic_write_json(destination / SNAPSHOT_METADATA_FILENAME, metadata)
    return metadata


__all__ = [
    "build_markov_snapshots",
    "SNAPSHOT_METADATA_FILENAME",
    "DEFAULT_DESTINATION_ROOT",
    "DEFAULT_TMP_ROOT",
    "DEFAULT_WINDOWS",
]
