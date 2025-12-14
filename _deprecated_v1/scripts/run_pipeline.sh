#!/bin/bash
# Pipeline build + analytics update runner
# Usage: ./scripts/run_pipeline.sh
# Usage: ./scripts/run_pipeline.sh > logs/pipeline_$(date +"%Y%m%d_%H%M").log 2>&1

pytest -q
ls data/features
python cli/mie.py build-features --mode full
python cli/mie.py update-features --lookback 90
python cli/mie.py ensure-markov-available --ticker SPY --window 2Y
python cli/mie.py update-all-analytics
ls data/analytics/markov/SPY/matrices/*/*/2Y*