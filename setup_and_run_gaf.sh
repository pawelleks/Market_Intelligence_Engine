#!/bin/bash

# This script ensures dependencies are installed in the CURRENT active python environment
# and then runs the GAF training and prediction.

echo "Detected Python: $(which python3)"
echo "Installing dependencies..."
# Reverting to standard tensorflow as tensorflow-macos not available for Py3.13
python3 -m pip install setuptools wheel
python3 -m pip install tensorflow pyts

if [ $? -eq 0 ]; then
    echo "Dependencies installed successfully."
    echo "Starting GAF Training..."
    export PYTHONPATH=src
    # Fix for potential TensorFlow freezing on Mac (OpenMP Deadlock)
    export TF_ENABLE_ONEDNN_OPTS=0
    export KMP_DUPLICATE_LIB_OK=TRUE
    export OMP_NUM_THREADS=1
    # FORCE CPU ONLY (Hide GPU from TF) to avoid Metal plugin deadlocks
    export CUDA_VISIBLE_DEVICES=-1
    python3 -m mie_lib.cli.mie train-gaf --epochs 50 --ticker SPY
    
    echo "Starting Daily Prediction..."
    python3 -m mie_lib.cli.mie build-gaf-daily --ticker SPY
    
    echo "Done! Check the GAF Neural Net page."
else
    echo "Failed to install dependencies."
    exit 1
fi
