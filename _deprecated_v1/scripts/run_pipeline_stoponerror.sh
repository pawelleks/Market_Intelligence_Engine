#!/bin/bash
set -euo pipefail

pytest -q --maxfail=1 --tb=short 2>&1 | tee "logs/tests_$(date +'%Y%m%d_%H%M').log"

ls data/features || true
python cli/mie.py build-features --mode full
python cli/mie.py update-features --lookback 90
python cli/mie.py ensure-markov-available --ticker SPY --window 2Y
python cli/mie.py update-all-analytics

ls data/analytics/markov/SPY/matrices/*/*/2Y* | tee -a "logs/tests_$(date +'%Y%m%d_%H%M').log"