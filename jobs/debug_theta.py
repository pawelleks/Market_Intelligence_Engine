import os
from thetadata import ThetaClient, StockReqType, DateRange
from datetime import date, timedelta
import logging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

# Use credentials if available, otherwise it connects to the local terminal
theta_host = os.environ.get("THETA_HOST", "theta_terminal")
client = ThetaClient(
    username=os.environ.get("THETADATA_USERNAME"),
    passwd=os.environ.get("THETADATA_PASSWORD"),
    host=theta_host,
    launch=False
)

def debug_symbol(symbol, is_index=True):
    print(f"\n--- DEBUGGING {symbol} (Index={is_index}) ---")
    with client.connect():
        # Test variations of the root
        roots = [symbol]
        if is_index and not symbol.startswith('$'):
            roots.append('$' + symbol)
            
        for r in roots:
            print(f"\n>> Testing Root: {r}")
            # 1. Try Manual LAST QUOTE (sec=INDEX)
            try:
                msg = f"MSG_CODE=1&root={r}&sec=INDEX&req=101"
                print(f"Trying manual LAST QUOTE (INDEX): {msg}")
                res = client.get_req(msg)
                print(f"Manual LAST INDEX Response: {res if res is not None and not res.empty else 'Empty'}")
            except Exception as e:
                print(f"Error manual LAST INDEX: {e}")

            # 2. Try Manual HIST OHLC (sec=INDEX)
            try:
                start_date = (date.today() - timedelta(days=5)).strftime('%Y%m%d')
                end_date = date.today().strftime('%Y%m%d')
                msg = f"MSG_CODE=2&START_DATE={start_date}&END_DATE={end_date}&root={r}&sec=INDEX&req=104&rth=true&IVL=60000"
                print(f"Trying manual HIST OHLC (INDEX): {msg}")
                res = client.get_req(msg)
                print(f"Manual HIST INDEX Response count: {len(res) if res is not None else 0}")
                if res is not None and not res.empty:
                    print(f"Latest Close: {res.iloc[-1]['close'] if 'close' in res.columns else 'N/A'}")
            except Exception as e:
                print(f"Error manual HIST INDEX: {e}")

            # 3. Try library get_last_stock (QUOTE)
            try:
                print(f"Trying library get_last_stock (QUOTE) for {r}")
                res = client.get_last_stock(req=StockReqType.QUOTE, root=r)
                print(f"Library Response: {res if res is not None and not res.empty else 'Empty'}")
            except Exception as e:
                print(f"Error library LAST: {e}")

if __name__ == "__main__":
    # Test LIST of roots
    print("\n--- LISTING AVAILABLE INDEX ROOTS ---")
    with client.connect():
        try:
            msg = "MSG_CODE=1&sec=INDEX&req=1"
            res = client.get_req(msg)
            if res is not None and not res.empty:
                print(f"Available Index Roots: {res.iloc[:,0].tolist()[:50]}") # Show first 50
            else:
                print("No index roots found.")
        except Exception as e:
            print(f"Error listing roots: {e}")

    debug_symbol("SPX", True)
    debug_symbol("NDX", True)
    debug_symbol("SPY", False)
