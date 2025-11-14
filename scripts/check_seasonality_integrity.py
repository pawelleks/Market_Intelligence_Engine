#!/usr/bin/env python
"""Wrapper to run seasonality integrity checks per ARCHITECT_BIBLE.

This delegates to scripts/validate_seasonality_alignment.py and uses its exit code.
"""
from __future__ import annotations
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_seasonality_alignment.py"

def main(argv: list[str]) -> int:
    if not VALIDATOR.exists():
        print(f"[ERROR] Missing validator: {VALIDATOR}")
        return 2
    cmd = [sys.executable, str(VALIDATOR)]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT))
        return proc.returncode
    except Exception as e:
        print(f"[ERROR] Failed to run validator: {e}")
        return 3

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

