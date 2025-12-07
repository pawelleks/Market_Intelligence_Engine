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
python -m mie_lib.cli.mie build-markov-grid --state-modes binary,tri --thresholds 0,5,10,15,20,25,30,35,40,45,50 --windows 1Y,2Y,5Y --orders 1,2

# 5. Update Seasonality Data
echo "[$(date)] Running update-seasonality..."
python -m mie_lib.cli.mie update-seasonality

echo "[$(date)] Daily Update Completed Successfully."
