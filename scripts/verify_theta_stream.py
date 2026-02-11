import asyncio
import os
from thetadata import ThetaClient, StreamMsg, StreamMsgType

async def main():
    print("Initializing Theta Stream verifier...")
    client = ThetaClient(
        username=os.getenv("THETA_USER", "default"),
        passwd=os.getenv("THETA_PASS", "default"),
        launch=False,
        host=os.getenv("THETA_HOST", "theta_terminal"),
        port=11000,
        streaming_port=10000,
        timeout=5
    )
    
    import thetadata
    print("thetadata dir:", dir(thetadata))
    try:
        if hasattr(thetadata, 'SecType'):
            print("SecType.STOCK:", thetadata.SecType.STOCK.value)
            print("SecType.INDEX:", thetadata.SecType.INDEX.value)
            print("SecType.OPTION:", thetadata.SecType.OPTION.value)
        if hasattr(thetadata, 'StockReqType'):
            print("StockReqType Members:", dir(thetadata.StockReqType))
            if hasattr(thetadata.StockReqType, 'TRADE'):
                 print("StockReqType.TRADE:", thetadata.StockReqType.TRADE.value)
    except Exception as e:
        print(f"Enum inspection failed: {e}")
    
    def on_msg(msg: StreamMsg):
        if msg.type == StreamMsgType.TRADE:
            print(f"TRADE RECEIVED: {msg.contract.root} @ {msg.trade.price} size={msg.trade.size}")
        elif msg.type == StreamMsgType.QUOTE:
            print(f"QUOTE RECEIVED: {msg.contract.root}")
        else:
            print(f"MSG: {msg.type}")

    print("Connecting to Stream...")
    # Returns a thread, non-blocking
    thread = client.connect_stream(on_msg)
    
    print("Subscribing to SPY (Stock)...")
    # Wait a bit for connection
    await asyncio.sleep(2)
    
    req_id = 1
    print("Subscribing to SPY (Stock) with multiple codes...")
    await asyncio.sleep(2)
    
    # Try 1: Trade (req=201) with valid dummy date
    # Format: YYYYMMDD
    print("Sending req=201 (Trade) with exp=20220101...")
    msg1 = "MSG_CODE=210&root=SPY&sec=STOCK&req=201&exp=20220101&strike=0&right=C&id=10\n"
    client._stream_server.sendall(msg1.encode("utf-8"))

    # Try 2: Quote (req=101) for fallback check
    print("Sending req=101 (Quote) with exp=20220101...")
    msg2 = "MSG_CODE=210&root=SPY&sec=STOCK&req=101&exp=20220101&strike=0&right=C&id=11\n"
    client._stream_server.sendall(msg2.encode("utf-8"))

    # Try 3: Option Chain with same dummy
    print("Sending sec=OPTION with exp=20220101...")
    msg3 = "MSG_CODE=210&root=SPY&sec=OPTION&req=201&exp=20220101&strike=0&right=C&id=12\n"
    client._stream_server.sendall(msg3.encode("utf-8"))
    
    print("Waiting for data (30 seconds)...")
    await asyncio.sleep(30)
    
    print("Closing...")

if __name__ == "__main__":
    asyncio.run(main())
