"""
Maintenance entrypoint to rebuild offline analytics end-to-end.

Steps (idempotent, offline-only):
  1) Update raw prices for all configured tickers (config/tickers.yml)
  2) Rebuild features for all tickers
  3) Build full Markov grid (modes/thresholds/windows/orders)
  4) Build HMM grid (standard 5-year window, 2 & 3 states)

Run:
  python scripts/rebuild_all_analytics.py

This script follows ARCHITECT_BIBLE rules: offline, deterministic, no UI, no network beyond ingest provider。
It relies on existing CLI commands and their defaults; no analytics math is altered here.
"""
from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path
from typing import List

# --- Resolve repository root and chdir there ---
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
if Path.cwd() != REPO_ROOT:
    try:
        # Ensure we run commands from repo root so relative paths work
        import os
        os.chdir(REPO_ROOT)
    except Exception:
        pass
# Make project modules importable (src/, cli/)
sys.path.insert(0, str(REPO_ROOT))

# Prefer project config loader / tickers reader for consistency
try:
    from src.data_ingest.yfinance_loader import read_tickers  # robust to config structure
except Exception:  # fallback: minimal YAML loader
    read_tickers = None

try:
    import yaml  # noqa: F401
except Exception:
    yaml = None  # fallback only; we prefer project utilities


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_all_tickers_from_config() -> List[str]:
    """
    Read config/tickers.yml and return a sorted list of unique tickers
    that should be processed by analytics.

    Implementation prefers the project's tickers reader for consistency.
    Logs the final list at INFO level.
    """
    tickers: List[str] = []
    try:
        if read_tickers is not None:
            tickers = [t.strip().upper() for t in read_tickers() if str(t).strip()]
        else:
            # Very light fallback: parse YAML top-level list or {tickers: [...]} structure
            cfg_path = REPO_ROOT / "config" / "tickers.yml"
            if cfg_path.exists() and yaml is not None:
                data = yaml.safe_load(cfg_path.read_text())
                if isinstance(data, list):
                    tickers = [str(t).strip().upper() for t in data if str(t).strip()]
                elif isinstance(data, dict) and isinstance(data.get("tickers"), list):
                    tickers = [str(t).strip().upper() for t in data.get("tickers", []) if str(t).strip()]
    except Exception as e:
        logging.warning("Failed to load tickers from config: %s", e)
    # Deduplicate and sort
    uniq = sorted({t for t in tickers if t})
    logging.info("Loaded %d tickers from config/tickers.yml: %s", len(uniq), uniq)
    return uniq


def run(cmd: list[str], desc: str) -> None:
    """Run a subprocess command with logging and strict error handling.

    - Logs start/end
    - Captures stdout/stderr; on failure, logs and exits with non-zero code.
    """
    logging.info("[RUN] %s: %s", desc, " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        logging.info(proc.stdout.strip())
    if proc.returncode != 0:
        logging.error("[FAIL] %s (code=%s)%s", desc, proc.returncode, f"\n{proc.stderr}" if proc.stderr else "")
        raise SystemExit(proc.returncode)
    logging.info("[OK] %s", desc)


def main():
    _setup_logging()
    logging.info("Starting full analytics rebuild...")

    tickers = load_all_tickers_from_config()
    if not tickers:
        logging.error("No tickers found in config/tickers.yml. Aborting.")
        raise SystemExit(2)

    # 1) Update RAW for all tickers (CLI loops over config internally)
    run([sys.executable, "cli/mie.py", "update-raw"], desc="Update raw data for configured tickers")

    # 2) Build / update FEATURES for all tickers
    # Prefer a single global build if supported (it uses config/tickers.yml internally)
    run([sys.executable, "cli/mie.py", "build-features", "--mode", "full", "--csv"], desc="Build features (full) for all tickers")

    # 3) Build Markov GRID (use CLI defaults for full grid; pass tickers only)
    run([
        sys.executable,
        "cli/mie.py",
        "build-markov-grid",
        "--tickers",
        ",".join(tickers),
    ], desc="Build Markov grid for configured tickers (defaults: modes=binary,tri; thresholds=0..150/5; windows=1Y..MAX; orders=1..4)")

    # 4) Build HMM GRID (standardized 5-year window, states 2 & 3)
    run([
        sys.executable,
        "cli/mie.py",
        "build-hmm-grid",
        "--tickers",
        ",".join(tickers),
        "--windows",
        "5",
        "--states",
        "2,3",
    ], desc="Build HMM grid (win=5y, states=2,3)")

    logging.info("All steps completed successfully.")


if __name__ == "__main__":
    main()

