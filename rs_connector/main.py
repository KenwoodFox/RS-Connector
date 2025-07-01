import os
import time
import logging
import coloredlogs
import asyncio
from .streamer import Streamer
from .api_client import APIClient


def main():
    # Configure logging
    coloredlogs.install(
        level="INFO", fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    # Get environment variables
    video_device = os.environ.get("VIDEO_DEVICE", "rs_connector/test_pattern.jpg")
    stream_type = os.environ.get("STREAM_TYPE", "jsmpeg").lower()
    stream_key = os.environ.get("STREAM_KEY", "")
    robot_id = os.environ.get("ROBOT_ID")
    api_url = os.environ.get("API_URL")
    ffmpeg_opts = os.environ.get("FFMPEG_OPTS", "")
    xres = int(os.environ.get("VIDEO_XRES", 768))
    yres = int(os.environ.get("VIDEO_YRES", 432))
    framerate = int(os.environ.get("VIDEO_FRAMERATE", 25))
    kbps = int(os.environ.get("VIDEO_KBPS", 350))

    # Validate environment variables
    if not robot_id:
        logging.error("ROBOT_ID not set. Exiting.")
        return
    if not stream_key:
        logging.error("STREAM_KEY not set. Exiting.")
        return

    # Initialize streamer and API client
    streamer = Streamer(video_device, robot_id, stream_key, ffmpeg_opts)
    api_client = APIClient(robot_id, stream_key, api_url)

    max_restarts = 5
    restart_attempts = 0

    try:
        # Start API Client
        api_client.start()
        # Wait for API to settle by waiting for pong
        if not api_client.wait_for_pong(timeout=10):
            logging.error("Did not receive pong from control WebSocket. Exiting.")
            return

        while True:
            if stream_type == "rtmp":
                streamer.start_stream()
            elif stream_type == "jsmpeg":
                video_endpoint = api_client.get_jsmpeg_video_endpoint()
                if not video_endpoint:
                    logging.error(
                        "Could not get robot video endpoint. Retrying in 10s."
                    )
                    time.sleep(10)
                    restart_attempts += 1
                    if restart_attempts >= max_restarts:
                        logging.error("Max ffmpeg restart attempts reached. Exiting.")
                        break
                    continue
                streamer.stream_key = stream_key or video_endpoint.get("identifier", "")
                streamer.start_jsmpeg_stream(
                    video_endpoint, xres=xres, yres=yres, framerate=framerate, kbps=kbps
                )
            else:
                logging.error(f"Unknown STREAM_TYPE: {stream_type}")
                return

            while streamer.is_running():
                time.sleep(1)

            logging.error("ffmpeg process not running!")
            restart_attempts += 1
            if restart_attempts >= max_restarts:
                logging.error("Max ffmpeg restart attempts reached. Exiting.")
                break
            logging.info("Attempting to restart ffmpeg in 5 seconds...")
            time.sleep(5)

    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        streamer.stop_stream()
        api_client.stop()


if __name__ == "__main__":
    main()
