import os
import time
import logging
import coloredlogs
from .streamer import Streamer
from .api_client import APIClient


def main():
    # Configure logging
    coloredlogs.install(
        level="INFO", fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    # Get environment variables
    video_device = os.environ.get("VIDEO_DEVICE", "rs_connector/test_pattern.jpg")
    stream_key = os.environ.get("STREAM_KEY", "")
    robot_id = os.environ.get("ROBOT_ID")
    api_url = os.environ.get("API_URL")
    ffmpeg_opts = os.environ.get("FFMPEG_OPTS", "")

    # Validate environment variables
    if not stream_key:
        logging.error("STREAM_KEY not set. Exiting.")
        return
    if not robot_id:
        logging.error("ROBOT_ID not set. Exiting.")
        return

    # Initialize streamer and API client
    streamer = Streamer(video_device, robot_id, stream_key, ffmpeg_opts)
    api_client = APIClient(api_url, robot_id)

    # Main loop
    try:
        # Start streaming
        streamer.start_stream()

        # API client loop
        while True:
            api_client.post_status({"status": "online"})
            connected = streamer.is_running()
            bitrate = streamer.get_bitrate() or "unknown"
            if connected:
                logging.debug(f"Connected to RTMP. Bitrate: {bitrate}")
            else:
                logging.error("ffmpeg process not running!")
            time.sleep(10)

    # Wait for keyboard interrupt
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        streamer.stop_stream()


if __name__ == "__main__":
    main()
