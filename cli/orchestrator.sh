#!/bin/bash
# orchestrator.sh
# Automates the Daily Market Intelligence Engine Workflow
#
# Usage:
#   Run inside the API container:
#     ./orchestrator.sh
#   Or from host via docker-compose:
#     docker-compose exec api bash orchestrator.sh

# 1. Configuration & Variables
set -e  # Exit immediately if a command exits with a non-zero status.

DATA_DIR="data"
LOG_DIR="${DATA_DIR}/logs"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="${LOG_DIR}/pipeline_${TODAY}.log"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "${LOG_FILE}"
}

log "Starting Daily MIE Pipeline for ${TODAY}"
log "Logs will be written to ${LOG_FILE}"

# 2. Ingestion Phase ("Fetch")
log "=== Phase 1: Ingestion ==="

log "Running update-raw (Fetching historical prices)..."
python cli/mie.py update-raw >> "${LOG_FILE}" 2>&1
log "update-raw completed successfully."

log "Running fetch-options-snapshot (Fetching daily GEX data)..."
python cli/mie.py fetch-options-snapshot >> "${LOG_FILE}" 2>&1
log "fetch-options-snapshot completed successfully."

# 3. Feature Engineering Phase
log "=== Phase 2: Feature Engineering ==="

log "Running build-features (Calculating technicals)..."
# Using --mode full to ensure complete consistency, though update is faster
python cli/mie.py build-features --mode full >> "${LOG_FILE}" 2>&1
log "build-features completed successfully."

# 4. Analytics Phase (Analysis)
log "=== Phase 3: Analytics Generation ==="

# Note: These can run in parallel if simple backgrounding & wait is used,
# but for safety and clear logging, we run sequentially here.

log "Running build-expected-moves (Daily/Weekly/Monthly ranges)..."
python cli/mie.py build-expected-moves --ticker @config --start "${TODAY}" >> "${LOG_FILE}" 2>&1
log "build-expected-moves completed."

log "Running build-markov-snapshots (States & Predictions)..."
python cli/mie.py build-markov-snapshots >> "${LOG_FILE}" 2>&1
log "build-markov-snapshots completed."

log "Running build-hmm-snapshots (Regime Classification)..."
python cli/mie.py build-hmm-snapshots >> "${LOG_FILE}" 2>&1
log "build-hmm-snapshots completed."

log "Running build-gex-daily (Gamma Exposure)..."
python cli/mie.py build-gex-daily --date "${TODAY}" >> "${LOG_FILE}" 2>&1
log "build-gex-daily completed."

log "Running build-gaf-daily (Neural Net Prediction)..."
python cli/mie.py build-gaf-daily >> "${LOG_FILE}" 2>&1
log "build-gaf-daily completed."

log "=== Pipeline Completed Successfully ==="
log "All artifacts generated for ${TODAY}."
