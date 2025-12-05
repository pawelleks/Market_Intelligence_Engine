import sys
import logging
from datetime import date, datetime, timezone
sys.path.append("src")

logging.basicConfig(level=logging.INFO)

from mie_lib.analytics.expected_moves.data_ingest import get_target_expirations
from mie_lib.utils.trading_calendar import is_trading_day

print("--- DIAGNOSTIC START ---")
now_utc = datetime.now(timezone.utc)
today = date.today()
print(f"System Time (UTC): {now_utc}")
print(f"Local Date (date.today()): {today}")

print(f"Is today ({today}) a trading day? {is_trading_day(today)}")

print("Calling get_target_expirations(today)...")
odte, weekly, monthly = get_target_expirations(today)
print(f"Result: ODTE={odte}, Weekly={weekly}, Monthly={monthly}")

if odte != today:
    print("MISMATCH: ODTE should be Today!")
else:
    print("MATCH: ODTE is Today.")
print("--- DIAGNOSTIC END ---")
