import os
from thetadata import ThetaClient, StockReqType, DateRange
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

def debug_spx():
    username = os.getenv("THETADATA_USERNAME")
    passwd = os.getenv("THETADATA_PASSWORD")
    theta_host = os.getenv("THETA_HOST", "mie-theta")
    
    if passwd and len(passwd) > 2:
        if (passwd.startswith("'") and passwd.endswith("'")) or (passwd.startswith('"') and passwd.endswith('"')):
            passwd = passwd[1:-1]

    client = ThetaClient(username=username, passwd=passwd, host=theta_host, launch=False, timeout=10)
    with client.connect():
        symbol = 'SPX'
        print(f"--- Debugging {symbol} ---")
        
        # 1. Last Trade
        try:
            res = client.get_last_stock(req=StockReqType.TRADE, root=symbol)
            print(f"TRADE:\n{res}")
        except Exception as e:
            print(f"TRADE error: {e}")
            
        # 2. Last Quote
        try:
            res = client.get_last_stock(req=StockReqType.QUOTE, root=symbol)
            print(f"QUOTE:\n{res}")
        except Exception as e:
            print(f"QUOTE error: {e}")
            
        # 3. Hist OHLC (1-min bars for precision)
        try:
            res = client.get_hist_stock(
                req=StockReqType.OHLC, 
                root=symbol, 
                date_range=DateRange(date.today() - timedelta(days=2), date.today()),
                interval_size=60000 # 1 min
            )
            print(f"Hist OHLC (First 5):\n{res.head()}")
            print(f"Hist OHLC (Last 5):\n{res.tail()}")
            
            # Normalize and check close
            if res is not None and not res.empty:
                res.columns = [c.name.lower() if hasattr(c, 'name') else str(c).lower() for c in res.columns]
                # Filter rows where close > 0
                valid = res[res['close'] > 0]
                if not valid.empty:
                    print(f"Latest valid CLOSE: {valid.iloc[-1]['close']}")
                else:
                    print("No valid CLOSE > 0 found in the last 2 days.")
        except Exception as e:
            print(f"Hist OHLC error: {e}")

if __name__ == "__main__":
    debug_spx()
