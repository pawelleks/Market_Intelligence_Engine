import yfinance as yf
import sys

def test_spy():
    print("Fetching SPY Ticker...")
    spy = yf.Ticker("SPY")
    
    print("Fetching History (Price)...")
    try:
        hist = spy.history(period="1d")
        if hist.empty:
            print("History Empty!")
        else:
            print(f"Latest Price: {hist['Close'].iloc[-1]}")
    except Exception as e:
        print(f"History Error: {e}")

    print("Fetching Options...")
    try:
        opts = spy.options
        if not opts:
            print("Options Empty!")
            return
        
        print(f"Found {len(opts)} expirations. First: {opts[0]}")
        
        chain = spy.option_chain(opts[0])
        print(f"Calls: {len(chain.calls)}, Puts: {len(chain.puts)}")
        
        call_oi = chain.calls['openInterest'].sum()
        put_oi = chain.puts['openInterest'].sum()
        
        print(f"Total Call OI: {call_oi}")
        print(f"Total Put OI: {put_oi}")
        
        if call_oi == 0 and put_oi == 0:
            print("WARNING: ALL OI IS ZERO.")
            
    except Exception as e:
        print(f"Options Error: {e}")

if __name__ == "__main__":
    test_spy()
