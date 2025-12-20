import yfinance as yf
t = yf.Ticker("^VIX1Y")
hist = t.history(period="1mo")
print(f"Ticker: ^VIX1Y")
print(f"Empty: {hist.empty}")
if not hist.empty:
    print(hist.head())
