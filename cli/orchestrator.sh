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

# Python Detection (Robust)
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif [ -x "/app/.venv/bin/python" ]; then
    PY="/app/.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PY="python3"
else
    PY="python"
fi

# Define CLI Command Wrapper
MIE_CMD="${PY} -m mie_lib.cli.mie"

log "Detected Python: ${PY}"

log "Starting Daily MIE Pipeline for ${TODAY}"
log "Logs will be written to ${LOG_FILE}"

# 1.5. Initialize Audit Log (Reset for new run)
RUN_TYPE=${1:-"MANUAL"} # Default to MANUAL if not provided
log "Initializing Audit Log (Type: ${RUN_TYPE})..."
JOB_TIME=$(date +%H:%M:%S)
${MIE_CMD} start-pipeline-job --name "Daily Pipeline ${TODAY} ${JOB_TIME}" --type "${RUN_TYPE}" >> "${LOG_FILE}" 2>&1
log "Audit Log Initialized."

# 2. Ingestion Phase ("Fetch")
log "=== Phase 1: Ingestion ==="

log "Running update-raw (Fetching historical prices)..."
${MIE_CMD} update-raw >> "${LOG_FILE}" 2>&1
log "update-raw completed successfully."

log "Step 2: Daily Options Snapshot (Download & Extract)"
log "---------------------------------------------------"
log "Running fetch-massive-snapshot (Download Full File)..."
${MIE_CMD} fetch-massive-snapshot >> "${LOG_FILE}" 2>&1
log "Download completed."

log "Running extract-massive-snapshot (Extract Configured Tickers)..."
${MIE_CMD} extract-massive-snapshot --tickers @config >> "${LOG_FILE}" 2>&1
log "Extraction completed."

# 3. Feature Engineering Phase
log "=== Phase 2: Feature Engineering ==="

log "Running build-features (Calculating technicals)..."
# Using --mode update for efficiency in daily cron, full is too heavy
${MIE_CMD} build-features --mode update --lookback 90 >> "${LOG_FILE}" 2>&1
log "build-features completed successfully."

# 3. Update Minervini Scanner
log "=== Phase 3: Scanners & Analytics ==="
log "Running build-minervini-daily..."
${MIE_CMD} build-minervini-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-minervini-daily completed."

# 4. Update Markov Data
log "Running build-markov-grid (Updating Windows)..."
${MIE_CMD} build-markov-grid --state-modes binary,tri --thresholds 0,5,10,15,20,25,30,35,40,45,50 --windows 1Y,2Y,5Y,10Y,15Y,MAX --orders 1,2 >> "${LOG_FILE}" 2>&1
${MIE_CMD} build-markov-snapshots --allow-missing >> "${LOG_FILE}" 2>&1
log "build-markov-grid completed."

# 5. Update HMM Data
log "Running build-hmm-daily..."
${MIE_CMD} build-hmm-daily --tickers @config >> "${LOG_FILE}" 2>&1
# log "Running build-hmm-grid..."
# ${MIE_CMD} build-hmm-grid --tickers @config --windows 5,10,20,MAX --states 2,3 >> "${LOG_FILE}" 2>&1
${MIE_CMD} build-hmm-snapshots --allow-missing >> "${LOG_FILE}" 2>&1
log "build-hmm-snapshots completed."

log "Running backtest-hmm (Generating Strategy Analysis)..."
${MIE_CMD} backtest-hmm --tickers @config >> "${LOG_FILE}" 2>&1
log "backtest-hmm completed."

# 6. Update GEX Data
log "Running build-gex-daily..."
${MIE_CMD} build-gex-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-gex-daily completed."

log "Running archive-gex-daily..."
${MIE_CMD} archive-gex-daily --tickers SPY >> "${LOG_FILE}" 2>&1
log "archive-gex-daily completed."

# 7. Update Expected Moves
log "Running update-expected-moves..."
${MIE_CMD} update-expected-moves --ticker @config --lookback 5 --include-weekly-reference >> "${LOG_FILE}" 2>&1
${MIE_CMD} build-expected-moves-snapshots --tickers @config >> "${LOG_FILE}" 2>&1
log "update-expected-moves completed."

log "Running update-expected-moves-v2 (Static)..."
${MIE_CMD} update-expected-moves-v2 >> "${LOG_FILE}" 2>&1
log "update-expected-moves-v2 completed."

log "Running analyze-expected-moves-reliability..."
${MIE_CMD} analyze-expected-moves-reliability >> "${LOG_FILE}" 2>&1
log "analyze-expected-moves-reliability completed."

# 8. Update Seasonality Data
log "Running update-seasonality..."
${MIE_CMD} update-seasonality >> "${LOG_FILE}" 2>&1
log "update-seasonality completed."

# 9. New Analytics (SMA Stack, ADX, PSAR)
log "Running update-sma-stack..."
${MIE_CMD} update-sma-stack >> "${LOG_FILE}" 2>&1
log "Running update-dcs..."
${MIE_CMD} update-dcs >> "${LOG_FILE}" 2>&1
log "Running update-adx..."
${MIE_CMD} update-adx >> "${LOG_FILE}" 2>&1
log "Running update-psar..."
${MIE_CMD} update-psar >> "${LOG_FILE}" 2>&1
log "Running update-ichimoku..."
${MIE_CMD} update-ichimoku >> "${LOG_FILE}" 2>&1
log "Running build-volatility-struct..."
${MIE_CMD} build-volatility-struct >> "${LOG_FILE}" 2>&1
log "Running update-volatility (ATR Analysis)..."
${MIE_CMD} update-volatility >> "${LOG_FILE}" 2>&1

# 8. Update FRED Calendar (Upcoming Releases)
# This script must run safely even if FRED API fails (it logs errors but doesn't crash)
log "Running update_fred_calendar..."
${PY} scripts/update_fred_calendar.py >> "${LOG_FILE}" 2>&1

# 9. Update Skew & PCR (Parallel)
log "Running build-skew-daily..."
${MIE_CMD} build-skew-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-skew-daily completed."

# 10. Time Series Momentum (TSMOM)
log "Running build-tsmom-daily..."
${MIE_CMD} build-tsmom-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-tsmom-daily completed."

# 11. GAF Prediction
log "Running build-gaf-daily..."
${MIE_CMD} build-gaf-daily >> "${LOG_FILE}" 2>&1
log "build-gaf-daily completed."

# 8d. Volume Regime
log "Running update-volume-regime..."
${MIE_CMD} update-volume-regime >> "${LOG_FILE}" 2>&1
log "update-volume-regime completed."

# 12. AI Context Generation
log "Running generate-ai-context..."
${MIE_CMD} update-stage --stage "AI Context Generation" --status "RUNNING"
# Generate logic needs a ticker, let's stick to SPY for now or iterate config
# For now, default to SPY as the primary context
if ${MIE_CMD} generate-ai-context --ticker SPY >> "${LOG_FILE}" 2>&1; then
    ${MIE_CMD} update-stage --stage "AI Context Generation" --status "COMPLETED"
    log "generate-ai-context completed."
else
    ${MIE_CMD} update-stage --stage "AI Context Generation" --status "FAILED"
    log "generate-ai-context FAILED."
fi

# 12b. AI Report Generation
log "Running generate-ai-report..."
${MIE_CMD} update-stage --stage "Daily Intelligence Report" --status "RUNNING"
if ${MIE_CMD} generate-ai-report --ticker SPY >> "${LOG_FILE}" 2>&1; then
    ${MIE_CMD} update-stage --stage "Daily Intelligence Report" --status "COMPLETED"
    log "generate-ai-report completed."
else
    ${MIE_CMD} update-stage --stage "Daily Intelligence Report" --status "FAILED"
    log "generate-ai-report FAILED."
fi

# 13. Finalize Status
log "Finalizing Audit Status..."
${MIE_CMD} update-stage --stage "Publish Analytics Data" --status "COMPLETED"
log "Finalizing Pipeline Job..."
${MIE_CMD} finish-pipeline-job --status "COMPLETED"
log "Audit finalized."

log "======================================================="
log "       🚀 DAILY UPDATE COMPLETED SUCCESSFULLY 🚀       "
log "======================================================="
log "All artifacts generated for ${TODAY}."
log "You can now view the latest data in the MIE Dashboard."
log "======================================================="
