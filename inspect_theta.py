from thetadata import ThetaClient
import os

def inspect_client():
    print("Inspecting ThetaClient...")
    client = ThetaClient(
        username="default", passwd="default", launch=False, 
        host=os.getenv("THETA_HOST", "theta_terminal"), 
        port=11000, streaming_port=10000, timeout=5
    )
    print(dir(client))

if __name__ == "__main__":
    inspect_client()
