import asyncio
import websockets
import json

async def listen():
    uri = "ws://localhost:8000/ws/spy?token=bypass@local.dev"  # Adjust if port/path differs in your setup
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for messages...")
            count = 0
            while count < 5:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"MSG {count+1}: {json.dumps(data, indent=2)}")
                count += 1
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(listen())
