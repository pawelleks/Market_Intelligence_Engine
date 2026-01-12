#!/usr/bin/env bash
# Economic Data Pipeline CRON Wrapper
# Robust wrapper: lockfile to avoid overlap, clear logging, venv-aware.
set -euo pipefail

# cd to repo root, assuming script lives in scripts/
cd "$(dirname "$0")/.."

mkdir -p logs
LOCKFILE="logs/economic_update.lock"
LOGFILE="logs/economic_pipeline_$(date +%F).log"

# lock (non-blocking). If running, exit gracefully.
if [ -e "${LOCKFILE}" ]; then
  echo "$(date +%FT%T%z) WARN  economic_cron: lockfile present (${LOCKFILE}); exiting." | tee -a "${LOGFILE}"
  exit 0
fi

touch "${LOCKFILE}"
cleanup() {
  rm -f "${LOCKFILE}"
}
trap cleanup EXIT

# Prefer venv python if available
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
  echo "$(date +%FT%T%z) WARN  economic_cron: .venv not found, using system python: ${PY}" | tee -a "${LOGFILE}"
fi

{
  echo "========== economic_pipeline start $(date +%FT%T%z) =========="
  echo "PY=${PY}"
  echo "PWD=$(pwd)"
  echo "PATH=${PATH}"

  # Add src to PYTHONPATH
  export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

  # Run economic pipeline
  ${PY} scripts/economic_pipeline.py

  echo "========== economic_pipeline end $(date +%FT%T%z) =========="
} | tee -a "${LOGFILE}"
