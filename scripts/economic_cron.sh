#!/usr/bin/env bash
# Economic Data Pipeline CRON Wrapper
# Robust wrapper: flock-based locking, clear logging, container-aware.
set -euo pipefail

# cd to repo root, assuming script lives in scripts/
cd "$(dirname "$0")/.."

mkdir -p logs
LOCKFILE="logs/economic_update.lock"
LOGFILE="logs/economic_pipeline_$(date +%F).log"

# Use flock for crash-safe locking. If another instance is running, exit gracefully.
exec 200>"${LOCKFILE}"
if ! flock -n 200; then
  echo "$(date +%FT%T%z) WARN  economic_cron: another instance is running; exiting." | tee -a "${LOGFILE}"
  exit 0
fi

# Detect Python: venv for local dev, system python in Docker containers
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -f "/.dockerenv" ] || grep -qsF docker /proc/1/cgroup 2>/dev/null; then
  PY="python"
else
  PY="python"
  echo "$(date +%FT%T%z) WARN  economic_cron: .venv not found, using system python" | tee -a "${LOGFILE}"
fi

{
  echo "========== economic_pipeline start $(date +%FT%T%z) =========="
  echo "PY=${PY}"
  echo "PWD=$(pwd)"

  # Add src to PYTHONPATH
  export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"

  # Run economic pipeline
  ${PY} scripts/economic_pipeline.py

  echo "========== economic_pipeline end $(date +%FT%T%z) =========="
} 2>&1 | tee -a "${LOGFILE}"
