import time
import logging
import asyncio
import websockets
import json
import threading
import requests


class APIClient:
    def __init__(
        self,
        robot_id,
        camera_id,
        stream_key,
        api_url=None,
        relay_host="0.0.0.0",
        relay_port=8765,
    ):
        # Setup variables
        self.robot_id = robot_id
        self.camera_id = camera_id
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

        # Relay server
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.relay_server = None
        self.relay_clients = set()

        # Pong event for main thread to wait on
        self.pong_event = threading.Event()

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

    # ================================
    # Relay server
    # ================================
    async def relay_handler(self, websocket):
        # Register client
        self.relay_clients.add(websocket)
        self.logger.info(f"Relay client connected: {websocket.remote_address}")
        try:
            await websocket.send(json.dumps({"rs_connector": time.time()}))
            await websocket.wait_closed()  # Keeps the handler alive until the client disconnects
        finally:
            self.relay_clients.remove(websocket)
            self.logger.info(f"Relay client disconnected: {websocket.remote_address}")

    async def start_relay_server(self):
        self.relay_server = await websockets.serve(
            self.relay_handler, self.relay_host, self.relay_port
        )
        self.logger.info(
            f"Relay WebSocket server started on ws://{self.relay_host}:{self.relay_port}"
        )

    async def send_to_relay_clients(self, message):
        # Forward message to all connected relay clients
        if self.relay_clients:
            self.logger.debug(
                f"Processing {len(self.relay_clients)} clients. Message: {message.rstrip()}"
            )
            try:
                for client in list(self.relay_clients):
                    try:
                        await client.send(message)
                        self.logger.debug(f"Sent to client: {client}")
                    except Exception as e:
                        self.logger.error(f"Error sending to client {client}: {e}")
            except Exception as e:
                self.logger.error(f"Exception during relay_clients iteration: {e}")

    # ================================
    # Websocket Client System
    # ================================
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
            # Start relay server
            await self.start_relay_server()
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
                            try:
                                j = json.loads(message)
                                if (
                                    j.get("command") == "RS_PONG"
                                    or j.get("type") == "RS_PING"
                                ):
                                    pong_time = asyncio.get_event_loop().time()
                                    self.pong_event.set()

                                # Forward to relay clients
                                await self.send_to_relay_clients(message)
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
                # Stop relay server
                self.relay_server.close()
                await self.relay_server.wait_closed()
                self.logger.info("Relay WebSocket server stopped.")
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")

    def send_camera_alive_message(self):
        """Send a camera alive message to the robotstreamer API every 5 seconds in a background thread."""

        def makePOST(url, data):
            try:
                resp = requests.post(url, json=data)
                self.logger.info(f"Camera alive POST {url} status {resp.status_code}")
            except Exception as e:
                self.logger.error(f"Could not make post to {url}: {e}")

        def alive_loop():
            url = f"{self.api_url}/v1/set_camera_status"
            while not getattr(self, "_stop_alive", False):
                self.logger.info("sending camera alive message")
                makePOST(
                    url,
                    {
                        "camera_id": self.camera_id,
                        "camera_status": "online",
                        "stream_key": self.stream_key,
                        "type": "robot_git",
                    },
                )
                for _ in range(5):
                    if getattr(self, "_stop_alive", False):
                        break
                    time.sleep(1)

        import threading, time

        self._stop_alive = False
        self._alive_thread = threading.Thread(target=alive_loop, daemon=True)
        self._alive_thread.start()

    def stop_camera_alive_message(self):
        self._stop_alive = True
        if hasattr(self, "_alive_thread"):
            self._alive_thread.join()

    def start(self):
        # Start the asyncio event loop in a background thread
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.ws_handler())

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self.logger.info("WebSocket client started.")
        self.send_camera_alive_message()

    def stop(self):
        # Signal async tasks to stop and wait for thread to finish
        self.stop_event.set()
        if self.async_stop_event:
            self.loop.call_soon_threadsafe(self.async_stop_event.set)
        if self.thread:
            self.thread.join()
        self.stop_camera_alive_message()
        self.logger.info("WebSocket client stopped.")

    def get_jsmpeg_endpoint(self, kind="video"):
        """
        Query the robotstreamer API for the jsmpeg video or audio endpoint for this robot.
        kind: 'video' or 'audio'
        """

        if kind == "video":
            endpoint = "jsmpeg_video_capture"
        elif kind == "audio":
            endpoint = "jsmpeg_audio_capture"
        else:
            raise ValueError(f"Unknown endpoint kind: {kind}")

        url = f"{self.api_url}/v1/get_endpoint/{endpoint}/{self.camera_id}"
        self.logger.info(f"Querying {kind} endpoint: {url}")
        try:
            resp = requests.get(url)
            data = resp.json()
            self.logger.info(f"{kind.capitalize()} endpoint response: {data}")
            return data  # Should contain 'host' and 'port'
        except Exception as e:
            self.logger.error(f"Failed to get jsmpeg {kind} endpoint: {e}")
            return None

    def get_jsmpeg_video_endpoint(self):
        return self.get_jsmpeg_endpoint("video")

    def get_jsmpeg_audio_endpoint(self):
        return self.get_jsmpeg_endpoint("audio")

    def wait_for_pong(self, timeout=10):
        return self.pong_event.wait(timeout)
