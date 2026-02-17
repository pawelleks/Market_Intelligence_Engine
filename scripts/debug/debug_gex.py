
import yfinance as yf
from datetime import date, timedelta, datetime

ticker = "SPY"
yf_ticker = yf.Ticker(ticker)
expirations = yf_ticker.options
print(f"Expirations for {ticker}: {expirations}")

today = date.today()
print(f"Today: {today}")

# Horizon Logic Copy
as_of = today
days_to_fri = (4 - as_of.weekday() + 7) % 7
if days_to_fri == 0: days_to_fri = 7
eow = as_of + timedelta(days=days_to_fri)
print(f"EOW: {eow}")

# Check first few expirations
for exp in expirations[:5]:
    try:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
        print(f"Exp: {exp}, EOW Match: {exp_date <= eow}")
    except Exception as e:
        print(f"Error parsing {exp}: {e}")
