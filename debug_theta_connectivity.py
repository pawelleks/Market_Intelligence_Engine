
import asyncio
import os
import logging
from mie_lib.realtime.theta_streamer import ThetaStreamer, StreamMsg, StreamMsgType

# Configure Logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("DebugTheta")

async def test_connectivity():
    print("--- STARTING CONNECTIVITY TEST ---")
    
    # 1. Initialize Streamer
    streamer = ThetaStreamer(["SPX"])
    
    # 2. Start (Connects and Subscribes)
    try:
        await streamer.start()
        print("✅ Connectivity Checks: Connected to Theta Terminal.")
    except Exception as e:
        print(f"❌ Connectivity Checks: Failed to connect. Error: {e}")
        return

    # 3. Wait for Data
    print("--- LISTENING FOR 10 SECONDS ---")
    
    # We intercept the loop callback to see what we get
    # streamer.broadcast_sync would be called.
    # But since we are running this script, we can just peek at internal state or logs.
    
    for i in range(10):
        await asyncio.sleep(1)
        if "SPX" in streamer.state:
            data = streamer.state["SPX"]
            print(f"[{i}s] State: {data}")
            if data.get("price", 0) > 0:
                 print("✅ RECIEVED STOCK PRICE UPDATE!")
            if data.get("net_flow", 0) != 0:
                 print("✅ RECIEVED OPTION FLOW UPDATE!")
        else:
            print(f"[{i}s] No state data yet...")

    await streamer.stop()
    print("--- TEST COMPLETE ---")

if __name__ == "__main__":
    try:
        asyncio.run(test_connectivity())
    except KeyboardInterrupt:
        pass
