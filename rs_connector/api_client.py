import logging
import asyncio
import websockets
import json
import threading
import requests


class APIClient:
    def __init__(self, robot_id, stream_key, api_url=None):
        # Setup variables
        self.robot_id = robot_id
        self.stream_key = stream_key
        self.api_url = api_url or "https://api.robotstreamer.com"

        # Setup logging
        self.logger = logging.getLogger("APIClient")

        # Setup websocket
        self.ws = None
        self.loop = None
        self.thread = None
        self.stop_event = threading.Event()  # For thread shutdown
        self.async_stop_event = None  # For async shutdown
        self.ping_task = None
        self.receive_task = None

    def get_control_host(self):
        # Try /v1/get_service/rscontrol first
        try:
            url = f"{self.api_url}/v1/get_service/rscontrol"
            resp = requests.get(url)
            data = resp.json()
            if data:
                data["protocol"] = "wss"
                self.logger.info(f"Got control host (service): {data}")
                return data
        except Exception as e:
            self.logger.warning(f"Failed to get_service/rscontrol: {e}")
        # Fallback to /v1/get_endpoint/rscontrol_robot/{robot_id}
        try:
            url = f"{self.api_url}/v1/get_endpoint/rscontrol_robot/{self.robot_id}"
            resp = requests.get(url)
            data = resp.json()
            if data:
                data["protocol"] = "ws"
                self.logger.info(f"Got control host (endpoint): {data}")
                return data
        except Exception as e:
            self.logger.error(f"Failed to get_endpoint/rscontrol_robot: {e}")
        return None

    async def ws_handler(self):
        # Async event for clean shutdown
        self.async_stop_event = asyncio.Event()
        h = self.get_control_host()
        if not h:
            self.logger.error(
                "Could not get control host, aborting WebSocket connection."
            )
            return
        # Connect to websocket (This URL from controller.py)
        url = f"{h['protocol']}://{h['host']}:{h['port']}/echo"
        self.logger.info(f"Connecting to control WebSocket: {url}")
        try:
            async with websockets.connect(url) as websocket:
                self.ws = websocket
                # Handshake
                if h["protocol"] == "wss":
                    # Construct a RS legal handshake
                    handshake = {
                        "type": "robot_connect",
                        "robot_id": self.robot_id,
                        "stream_key": self.stream_key,
                    }
                else:
                    handshake = {"command": self.stream_key}
                await websocket.send(json.dumps(handshake))
                self.logger.info(f"Sent handshake: {handshake}")

                # Track last pong time for ping-pong
                pong_time = asyncio.get_event_loop().time()

                async def ping_pong():
                    nonlocal pong_time
                    while not self.async_stop_event.is_set():
                        await asyncio.sleep(5)
                        try:
                            await websocket.send(json.dumps({"command": "RS_PING"}))
                            self.logger.debug("Sent RS_PING")
                        except Exception as e:
                            self.logger.error(f"Ping error: {e}")
                        # Check pong timeout
                        if asyncio.get_event_loop().time() - pong_time > 60:
                            self.logger.error(
                                "No RS_PONG received in 60s, closing connection."
                            )
                            await websocket.close()
                            break

                async def receive_loop():
                    nonlocal pong_time
                    try:
                        async for message in websocket:
                            # Log messages we get but only mark important/user messages as info
                            if "user" not in message:
                                self.logger.debug(f"Received: {message.rstrip()}")
                            else:
                                self.logger.info(f"Received: {message.rstrip()}")

                            # Check if we got a pong or ping
                            try:
                                j = json.loads(message)
                                if (
                                    j.get("command") == "RS_PONG"
                                    or j.get("type") == "RS_PING"
                                ):
                                    pong_time = asyncio.get_event_loop().time()
                            except Exception:
                                pass
                    except websockets.ConnectionClosed:
                        self.logger.info("WebSocket connection closed.")
                    except Exception as e:
                        self.logger.error(f"WebSocket receive error: {e}")

                # Start ping-pong and receive tasks
                self.ping_task = asyncio.create_task(ping_pong())
                self.receive_task = asyncio.create_task(receive_loop())

                # Wait for stop event
                await self.async_stop_event.wait()
                # Clean up
                self.logger.info("Shutting down WebSocket handler...")
                self.ping_task.cancel()
                self.receive_task.cancel()
                await websocket.close()
                self.logger.info("WebSocket closed cleanly.")
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")

    def start(self):
        # Start the asyncio event loop in a background thread
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.ws_handler())

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self.logger.info("WebSocket client started.")

    def stop(self):
        # Signal async tasks to stop and wait for thread to finish
        self.stop_event.set()
        if self.async_stop_event:
            self.loop.call_soon_threadsafe(self.async_stop_event.set)
        if self.thread:
            self.thread.join()
        self.logger.info("WebSocket client stopped.")
