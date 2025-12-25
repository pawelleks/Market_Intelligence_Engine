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

# 1.5. Initialize Audit Log (Reset for new run)
RUN_TYPE=${1:-"MANUAL"} # Default to MANUAL if not provided
log "Initializing Audit Log (Type: ${RUN_TYPE})..."
python -m mie_lib.cli.mie start-pipeline-job --name "Daily Pipeline ${TODAY}" --type "${RUN_TYPE}" >> "${LOG_FILE}" 2>&1
log "Audit Log Initialized."

# 2. Ingestion Phase ("Fetch")
log "=== Phase 1: Ingestion ==="

log "Running update-raw (Fetching historical prices)..."
python -m mie_lib.cli.mie update-raw >> "${LOG_FILE}" 2>&1
log "update-raw completed successfully."

log "Step 2: Daily Options Snapshot (Download & Extract)"
log "---------------------------------------------------"
log "Running fetch-massive-snapshot (Download Full File)..."
python -m mie_lib.cli.mie fetch-massive-snapshot >> "${LOG_FILE}" 2>&1
log "Download completed."

log "Running extract-massive-snapshot (Extract Configured Tickers)..."
python -m mie_lib.cli.mie extract-massive-snapshot --tickers @config >> "${LOG_FILE}" 2>&1
log "Extraction completed."

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
python -m mie_lib.cli.mie build-markov-snapshots --allow-missing >> "${LOG_FILE}" 2>&1
log "build-markov-grid completed."

# 5. Update HMM Data
log "Running build-hmm-daily..."
python -m mie_lib.cli.mie build-hmm-daily --tickers @config >> "${LOG_FILE}" 2>&1
# log "Running build-hmm-grid..."
# python -m mie_lib.cli.mie build-hmm-grid --tickers @config --windows 5,10,20,MAX --states 2,3 >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-hmm-snapshots --allow-missing >> "${LOG_FILE}" 2>&1
log "build-hmm-snapshots completed."

log "Running backtest-hmm (Generating Strategy Analysis)..."
python -m mie_lib.cli.mie backtest-hmm --tickers @config >> "${LOG_FILE}" 2>&1
log "backtest-hmm completed."

# 6. Update GEX Data
log "Running build-gex-daily..."
python -m mie_lib.cli.mie build-gex-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-gex-daily completed."

# 7. Update Expected Moves
log "Running update-expected-moves..."
python -m mie_lib.cli.mie update-expected-moves --ticker @config --lookback 5 --include-weekly-reference >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-expected-moves-snapshots --tickers @config >> "${LOG_FILE}" 2>&1
log "update-expected-moves completed."

# 8. Update Seasonality Data
log "Running update-seasonality..."
python -m mie_lib.cli.mie update-seasonality >> "${LOG_FILE}" 2>&1
log "update-seasonality completed."

# 9. New Analytics (SMA Stack, ADX, PSAR)
log "Running update-sma-stack..."
python -m mie_lib.cli.mie update-sma-stack >> "${LOG_FILE}" 2>&1
log "Running update-adx..."
python -m mie_lib.cli.mie update-adx >> "${LOG_FILE}" 2>&1
log "Running update-psar..."
python -m mie_lib.cli.mie update-psar >> "${LOG_FILE}" 2>&1
log "Running update-ichimoku..."
python -m mie_lib.cli.mie update-ichimoku >> "${LOG_FILE}" 2>&1
log "Running build-volatility-struct..."
python -m mie_lib.cli.mie build-volatility-struct >> "${LOG_FILE}" 2>&1
log "Running update-volatility (ATR Analysis)..."
python -m mie_lib.cli.mie update-volatility >> "${LOG_FILE}" 2>&1

# 10. Time Series Momentum (TSMOM)
log "Running build-tsmom-daily..."
python -m mie_lib.cli.mie build-tsmom-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-tsmom-daily completed."

# 11. GAF Prediction
log "Running build-gaf-daily..."
python -m mie_lib.cli.mie build-gaf-daily >> "${LOG_FILE}" 2>&1
log "build-gaf-daily completed."

# 12. AI Context Generation
log "Running generate-ai-context..."
python -m mie_lib.cli.mie generate-ai-context --ticker SPY >> "${LOG_FILE}" 2>&1
log "generate-ai-context completed."

# 13. Finalize Status
log "Finalizing Audit Status..."
python -m mie_lib.cli.mie update-stage --stage "Publish Analytics Data" --status "COMPLETED"
log "Finalizing Pipeline Job..."
python -m mie_lib.cli.mie finish-pipeline-job --status "COMPLETED"
log "Audit finalized."

log "======================================================="
log "       🚀 DAILY UPDATE COMPLETED SUCCESSFULLY 🚀       "
log "======================================================="
log "All artifacts generated for ${TODAY}."
log "You can now view the latest data in the MIE Dashboard."
log "======================================================="
