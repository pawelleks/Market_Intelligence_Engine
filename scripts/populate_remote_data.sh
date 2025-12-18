#!/bin/bash
set -e

# Data Population Script for MIE
# To be run INSIDE the mie-api container.

echo "==========================================="
echo "MIE Data Population (Remote)"
echo "==========================================="
export PYTHONPATH=$PYTHONPATH:.

# 1. Update Everything (Raw, Features, Markov Grid, HMM Grid, EM, GEX)
echo "[1/4] Running update-everything (Incremental)..."
python cli/mie.py update-everything

# 2. TSMOM Backfill (Explicit)
echo "[2/4] Backfilling TSMOM (History)..."
python cli/mie.py build-tsmom-daily --backfill --tickers @config

# 3. Minervini (Explicit)
echo "[3/4] Building Minervini Scanner..."
python cli/mie.py build-minervini-daily

# 4. Seasonality Base (Explicit)
echo "[4/4] Building Seasonality Base..."
python cli/mie.py build-seasonality-base --from-config

# 5. Reliability Rebuild (Just in case)
echo "[5/5] Rebuilding Reliability Pages..."
python cli/mie.py rebuild-reliability

echo "✅ Remote Data Population Complete."
