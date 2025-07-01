import asyncio
import websockets


async def test():
    uri = "ws://172.17.0.3:8765"
    async with websockets.connect(uri) as ws:
        print("Connected!")
        try:
            async for msg in ws:
                print("GOT:", msg)
        except Exception as e:
            print("Error in receive loop:", e)
        print("Connection closed.")


asyncio.run(test())
