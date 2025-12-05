import logging
import sys
from datetime import date, datetime, timedelta, timezone
# Add src to path
sys.path.append("src")

# Configure logging
logging.basicConfig(level=logging.INFO)

from mie_lib.analytics.expected_moves.engine import run_daily_em_build

# Just run a normal build for SPY to restore valid "Latest" state for today
print("--- restoring valid state for SPY ---")
run_daily_em_build(["SPY"])
print("Restored.")
