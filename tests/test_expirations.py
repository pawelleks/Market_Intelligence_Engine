from datetime import date, datetime
from mie_lib.analytics.expected_moves.data_ingest import get_target_expirations
from mie_lib.utils.trading_calendar import get_previous_trading_day

today = date.today()
print(f"Today: {today}")
odte, weekly, monthly = get_target_expirations(today)
print(f"ODTE: {odte}")
print(f"Weekly: {weekly}")
print(f"Monthly: {monthly}")

spot_date = get_previous_trading_day(odte)
print(f"Spot Date: {spot_date}")
