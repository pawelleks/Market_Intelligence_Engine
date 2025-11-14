#!/usr/bin/env bash
# Nightly incremental data update for Market_Intelligence_Engine
# Robust wrapper: lockfile to avoid overlap, clear logging, venv-aware.
set -euo pipefail

# cd to repo root, assuming script lives in scripts/
cd "$(dirname "$0")/.."

mkdir -p logs
LOCKFILE="logs/update.lock"
LOGFILE="logs/update_$(date +%F).log"

# lock (non-blocking). If running, exit gracefully.
if [ -e "${LOCKFILE}" ]; then
  echo "$(date -Is) WARN  nightly_update: lockfile present (${LOCKFILE}); exiting." | tee -a "${LOGFILE}"
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
  echo "$(date -Is) WARN  nightly_update: .venv not found, using system python: ${PY}" | tee -a "${LOGFILE}"
fi

{
  echo "========== nightly_update start $(date -Is) =========="
  echo "PY=${PY}"
  echo "PWD=$(pwd)"
  echo "PATH=${PATH}"

  # Run incremental pipeline
  ${PY} cli/mie.py update-everything

  echo "========== nightly_update end $(date -Is) =========="
} >> "${LOGFILE}" 2>&1
