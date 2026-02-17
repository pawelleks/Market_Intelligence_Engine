from thetadata import ThetaClient
import os

def check_connection():
    print("Initializing Theta Terminal Client...")
    client = ThetaClient(
        username=os.getenv("THETA_USER", "default"),
        passwd=os.getenv("THETA_PASS", "default"),
        launch=False,
        host=os.getenv("THETA_HOST", "theta_terminal"),
        port=11000,
        streaming_port=10000,
        timeout=5
    )
    
    print("Connecting...")
    try:
        # Use context manager for connection
        with client.connect():
            print("Connected! Fetching SPY Stock Quote (Last)...")
            # 101 = Quote, 201 = Trade. Let's try 101 (Quote) for SPY.
            response = client.get_last_stock(101, "SPY")
            print(f"SUCCESS: Stock Quote Response: {response}")
            
    except Exception as e:
        print(f"Connection/Request Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_connection()
