from mie_lib.analytics.seasonality_analytics import get_seasonality_forecast
from datetime import date

# Test for SPY starting today
print(get_seasonality_forecast("SPY", start_date=date.today(), days=5))
