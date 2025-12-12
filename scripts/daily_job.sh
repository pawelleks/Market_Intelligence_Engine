#!/bin/bash
set -e

# Daily Data Pipeline
echo "[$(date)] Starting Daily Data Update..."

export PYTHONPATH=/app/src

# 1. Update Raw Data (Incremental Fetch)
echo "[$(date)] Running update-raw..."
python -m mie_lib.cli.mie update-raw

# 2. Build Features
echo "[$(date)] Running build-features..."
python -m mie_lib.cli.mie build-features --mode update --lookback 90

# 3. Update Minervini Scanner (Dependent on latest price/MA)
echo "[$(date)] Running build-minervini-daily..."
python -m mie_lib.cli.mie build-minervini-daily --tickers @config

# 4. Update Markov Data (Dependent on features)
echo "[$(date)] Running build-markov-grid..."
python -m mie_lib.cli.mie build-markov-grid --state-modes binary,tri --thresholds 0,5,10,15,20,25,30,35,40,45,50 --windows 1Y,2Y,5Y,10Y,15Y,MAX --orders 1,2
python -m mie_lib.cli.mie build-markov-snapshots

# 5. Update HMM Data
echo "[$(date)] Running build-hmm-daily..."
python -m mie_lib.cli.mie build-hmm-daily --tickers @config
python -m mie_lib.cli.mie build-hmm-snapshots

# 6. Update GEX Data
echo "[$(date)] Running build-gex-daily..."
# Use Polygon Snapshot for accurate non-approximated data
python -m mie_lib.cli.mie fetch-polygon-snapshot --tickers @config || echo "Options fetch warning (ignoring)"
python -m mie_lib.cli.mie build-gex-daily --tickers @config

# 7. Update Expected Moves
echo "[$(date)] Running update-expected-moves..."
python -m mie_lib.cli.mie update-expected-moves --lookback 5 --include-weekly-reference
python -m mie_lib.cli.mie build-expected-moves-snapshots

# 7b. Run Reliability Analysis (Post-process Expected Moves)
echo "[$(date)] Running reliability-processor..."
python -m mie_lib.analytics.expected_moves.reliability_processor

# 8. Update Seasonality Data
echo "[$(date)] Running update-seasonality..."
python -m mie_lib.cli.mie update-seasonality

# 9. Update GAF Prediction
echo "[$(date)] Running build-gaf-daily..."
python -m mie_lib.cli.mie build-gaf-daily

echo "======================================================="
echo "       🚀 DAILY UPDATE COMPLETED SUCCESSFULLY 🚀       "
echo "======================================================="
echo "[$(date)] All artifacts generated."
echo "You can now view the latest data in the MIE Dashboard."
echo "======================================================="
