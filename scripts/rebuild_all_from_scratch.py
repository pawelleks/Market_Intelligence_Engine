"""
Full, from-scratch offline analytics rebuild for all tickers in config/tickers.yml.

This script intentionally performs a nuclear refresh:
  1) Fetch full raw history for each discovered ticker (overwrite parquet/csv)
  2) Build features in full mode
  3) Build Markov grid (states + matrices) for configured modes/thresholds/windows/orders
  4) Build standardized HMM grid

Run:
  python scripts/rebuild_all_from_scratch.py

Notes:
- Follows ARCHITECT_BIBLE: offline, deterministic, atomic file writes delegated to existing modules/CLI.
- Does not change analytics semantics. Uses existing ingest/features/analytics code paths.
- Robust ticker discovery tolerates mildly malformed config/tickers.yml.
"""
from __future__ import annotations
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

# Resolve repo root and chdir
SCRIPT = Path(__file__).resolve()
REPO_ROOT = SCRIPT.parent.parent
if Path.cwd() != REPO_ROOT:
    os.chdir(REPO_ROOT)
# Ensure project imports succeed
sys.path.insert(0, str(REPO_ROOT))

# Prefer importing project helpers (no UI)
try:
    from src.data_ingest.yfinance_loader import fetch_full_history
except Exception as e:  # pragma: no cover
    print(f"ERROR: cannot import fetch_full_history: {e}")
    raise

try:
    # Optional utility for YAML, but we tolerate malformed files with a fallback
    import yaml  # type: ignore
except Exception:
    yaml = None  # pragma: no cover

CONFIG_TICKERS = REPO_ROOT / "config" / "tickers.yml"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _clean_token(s: str) -> str:
    """Normalize a potential ticker token: strip bullets/prefixes and uppercase.
    Accept only reasonable ticker characters (letters/numbers/.-^). Return empty if invalid.
    """
    s0 = s.strip()
    # drop YAML bullet or stray prefix chars
    s0 = re.sub(r"^[\-*=+>\s]+", "", s0)
    # skip obvious non-ticker lines
    if ":" in s0:
        return ""
    # Allow letters, numbers, dot, hyphen, caret (common in some feeds)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9.\-^]{0,15}", s0):
        return ""
    return s0.upper()


def _fallback_parse_tickers_from_text(text: str) -> List[str]:
    toks: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tok = _clean_token(line)
        if tok:
            toks.append(tok)
    # Dedup while preserving order
    seen = set()
    out: List[str] = []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def load_all_analytics_tickers() -> List[str]:
    """Load all tickers for analytics from config/tickers.yml with robust fallback.
    Prefers YAML structure (list or {tickers:[...]}); falls back to line-based parsing
    tolerant of mildly malformed files.
    """
    if not CONFIG_TICKERS.exists():
        logging.error("Tickers config not found: %s", CONFIG_TICKERS)
        return []
    content = CONFIG_TICKERS.read_text()
    tickers: List[str] = []
    # Try YAML first
    if yaml is not None:
        try:
            data = yaml.safe_load(content)
            if isinstance(data, list):
                tickers = [_clean_token(str(t)) for t in data]
            elif isinstance(data, dict) and isinstance(data.get("tickers"), list):
                tickers = [_clean_token(str(t)) for t in data.get("tickers", [])]
            tickers = [t for t in tickers if t]
        except Exception:
            tickers = []
    # Fallback to text parse if YAML failed or yielded nothing (malformed file)
    if not tickers:
        tickers = _fallback_parse_tickers_from_text(content)
    # Finalize list: dedup + sort for deterministic iteration
    uniq_sorted = sorted(set(tickers))
    logging.info("Discovered %d tickers from config/tickers.yml: %s", len(uniq_sorted), uniq_sorted)
    return uniq_sorted


def run(cmd: List[str], desc: str) -> None:
    """Run a subprocess with logging and strict failure handling."""
    logging.info("[RUN] %s: %s", desc, " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        logging.info(proc.stdout.strip())
    if proc.returncode != 0:
        logging.error("[FAIL] %s (code=%s)%s", desc, proc.returncode, f"\n{proc.stderr}" if proc.stderr else "")
        raise SystemExit(proc.returncode)
    logging.info("[OK] %s", desc)


def _rebuild_raw_for_all(tickers: Iterable[str]) -> None:
    """Fetch full history for each ticker and overwrite outputs.
    Uses project ingest helper directly to avoid depending on potentially malformed
    config parsing inside the CLI.
    """
    for t in tickers:
        try:
            logging.info("[RAW] full fetch %s", t)
            res = fetch_full_history(t)
            logging.info("[RAW] %s", res)
        except SystemExit:
            raise
        except Exception as e:
            logging.warning("[RAW] WARN %s: %s", t, e)


def main() -> None:
    _setup_logging()
    logging.info("Starting full rebuild from scratch...")

    tickers = load_all_analytics_tickers()
    if not tickers:
        logging.error("No valid tickers found in config/tickers.yml; aborting.")
        raise SystemExit(2)

    # Step 1: Full RAW rebuild (direct function calls per ticker)
    _rebuild_raw_for_all(tickers)

    # Step 2: Full FEATURES rebuild (single CLI call)
    run([sys.executable, "cli/mie.py", "build-features", "--mode", "full", "--csv"], desc="Build features (full)")

    # Step 3: Full MARKOV grid (defaults cover modes=binary,tri; thresholds 0..150/5; windows 1Y..MAX; orders=1..4)
    run([
        sys.executable,
        "cli/mie.py",
        "build-markov-grid",
        "--tickers",
        ",".join(tickers),
    ], desc="Build Markov grid for all tickers")

    # Step 4: Full HMM grid (standard 5y, 2 & 3 states)
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
    ], desc="Build HMM grid (5y, states=2,3)")

    # Step 5 (optional but recommended): Build Seasonality base for all tickers
    try:
        run([sys.executable, "cli/mie.py", "build-seasonality-base", "--from-config"], desc="Build Seasonality base for all tickers")
    except SystemExit:
        raise
    except Exception as e:  # pragma: no cover
        logging.warning("Seasonality base build step failed or skipped: %s", e)

    logging.info("Full rebuild from scratch completed successfully.")


if __name__ == "__main__":
    main()
