import yfinance as yf
print("Testing ^VIX1Y:")
t = yf.Ticker("^VIX1Y")
hist = t.history(period="1mo")
print(f"Empty: {hist.empty}")

print("Testing VIX1Y:")
t2 = yf.Ticker("VIX1Y")
hist2 = t2.history(period="1mo")
print(f"Empty: {hist2.empty}")
