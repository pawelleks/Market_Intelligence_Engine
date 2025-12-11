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
python -m mie_lib.cli.mie update-raw >> "${LOG_FILE}" 2>&1
log "update-raw completed successfully."

log "Running fetch-options-snapshot (Fetching daily GEX data)..."
python -m mie_lib.cli.mie fetch-options-snapshot || echo "Options fetch warning" >> "${LOG_FILE}" 2>&1
log "fetch-options-snapshot completed successfully."

# 3. Feature Engineering Phase
log "=== Phase 2: Feature Engineering ==="

log "Running build-features (Calculating technicals)..."
# Using --mode update for efficiency in daily cron, full is too heavy
python -m mie_lib.cli.mie build-features --mode update --lookback 90 >> "${LOG_FILE}" 2>&1
log "build-features completed successfully."

# 3. Update Minervini Scanner
log "=== Phase 3: Scanners & Analytics ==="
log "Running build-minervini-daily..."
python -m mie_lib.cli.mie build-minervini-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-minervini-daily completed."

# 4. Update Markov Data
log "Running build-markov-grid (Updating Windows)..."
python -m mie_lib.cli.mie build-markov-grid --state-modes binary,tri --thresholds 0,5,10,15,20,25,30,35,40,45,50 --windows 1Y,2Y,5Y,10Y,15Y,MAX --orders 1,2 >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-markov-snapshots >> "${LOG_FILE}" 2>&1
log "build-markov-grid completed."

# 5. Update HMM Data
log "Running build-hmm-daily..."
python -m mie_lib.cli.mie build-hmm-daily --tickers @config >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-hmm-snapshots >> "${LOG_FILE}" 2>&1
log "build-hmm-snapshots completed."

# 6. Update GEX Data
log "Running build-gex-daily..."
python -m mie_lib.cli.mie build-gex-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-gex-daily completed."

# 7. Update Expected Moves
log "Running update-expected-moves..."
python -m mie_lib.cli.mie update-expected-moves --lookback 5 --include-weekly-reference >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-expected-moves-snapshots >> "${LOG_FILE}" 2>&1
log "update-expected-moves completed."

# 8. Update Seasonality Data
log "Running update-seasonality..."
python -m mie_lib.cli.mie update-seasonality >> "${LOG_FILE}" 2>&1
log "update-seasonality completed."

# 9. GAF Prediction
log "Running build-gaf-daily..."
python -m mie_lib.cli.mie build-gaf-daily >> "${LOG_FILE}" 2>&1
log "build-gaf-daily completed."

log "======================================================="
log "       🚀 DAILY UPDATE COMPLETED SUCCESSFULLY 🚀       "
log "======================================================="
log "All artifacts generated for ${TODAY}."
log "You can now view the latest data in the MIE Dashboard."
log "======================================================="
