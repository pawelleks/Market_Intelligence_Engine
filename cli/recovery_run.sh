#!/bin/bash
set -e
export PYTHONPATH=/app/src
DATA_DIR="data"
LOG_DIR="${DATA_DIR}/logs"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="${LOG_DIR}/pipeline_recovery_${TODAY}.log"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "${LOG_FILE}"
}

log "Resuming pipeline from Feature Engineering..."

# 3. Feature Engineering Phase
log "Running build-features (Calculating technicals)..."
# Using --mode update for efficiency
python -m mie_lib.cli.mie build-features --mode update --lookback 90 >> "${LOG_FILE}" 2>&1
log "build-features completed successfully."

# 4. Update Minervini Scanner
log "Running build-minervini-daily..."
python -m mie_lib.cli.mie build-minervini-daily --tickers @config >> "${LOG_FILE}" 2>&1
log "build-minervini-daily completed."

# 5. Update Markov Data
log "Running build-markov-grid..."
python -m mie_lib.cli.mie build-markov-grid --state-modes binary,tri --thresholds 0,5,10,15,20,25,30,35,40,45,50 --windows 1Y,2Y,5Y,10Y,15Y,MAX --orders 1,2 >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-markov-snapshots >> "${LOG_FILE}" 2>&1
log "build-markov-grid completed."

# 6. Update HMM Data
log "Running build-hmm-daily..."
python -m mie_lib.cli.mie build-hmm-daily --tickers @config >> "${LOG_FILE}" 2>&1
# log "Running build-hmm-grid..."
# python -m mie_lib.cli.mie build-hmm-grid --tickers @config --windows 5,10,20,MAX --states 2,3 >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-hmm-snapshots >> "${LOG_FILE}" 2>&1
log "build-hmm-snapshots completed."

# 7. Update GEX Data
log "Running build-gex-daily..."
python -m mie_lib.cli.mie build-gex-daily --date "${TODAY}" --tickers @config >> "${LOG_FILE}" 2>&1
log "build-gex-daily completed."

# 8. Update Expected Moves
log "Running update-expected-moves..."
python -m mie_lib.cli.mie update-expected-moves --ticker @config --lookback 5 --include-weekly-reference >> "${LOG_FILE}" 2>&1
python -m mie_lib.cli.mie build-expected-moves-snapshots --tickers @config >> "${LOG_FILE}" 2>&1
log "update-expected-moves completed."

# 9. Update Seasonality Data
log "Running update-seasonality..."
python -m mie_lib.cli.mie update-seasonality >> "${LOG_FILE}" 2>&1
log "update-seasonality completed."

# 10. New Analytics (SMA Stack, ADX, PSAR)
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

# 11. GAF Prediction
log "Running build-gaf-daily..."
python -m mie_lib.cli.mie build-gaf-daily >> "${LOG_FILE}" 2>&1
log "build-gaf-daily completed."

log "======================================================="
log "       🚀 PIPELINE RECOVERY COMPLETED 🚀       "
log "======================================================="
