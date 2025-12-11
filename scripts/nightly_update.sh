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
  echo "$(date +%FT%T%z) WARN  nightly_update: lockfile present (${LOCKFILE}); exiting." | tee -a "${LOGFILE}"
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
  echo "$(date +%FT%T%z) WARN  nightly_update: .venv not found, using system python: ${PY}" | tee -a "${LOGFILE}"
fi

{
  echo "========== nightly_update start $(date +%FT%T%z) =========="
  echo "PY=${PY}"
  echo "PWD=$(pwd)"
  echo "PATH=${PATH}"

  # Add src to PYTHONPATH so we can run the real CLI module
  export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

  # Run incremental pipeline using the real library CLI
  ${PY} -m mie_lib.cli.mie update-everything

  echo "========== nightly_update end $(date +%FT%T%z) =========="
} | tee -a "${LOGFILE}"
