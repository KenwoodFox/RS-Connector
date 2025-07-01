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
    api_client = APIClient(robot_id, stream_key, api_url)

    # Main loop
    try:
        # Start streaming
        streamer.start_stream()
        api_client.start()

        restart_attempts = 0
        max_restarts = 5

        # API client loop
        while True:
            connected = streamer.is_running()
            bitrate = streamer.get_bitrate() or "unknown"
            if connected:
                logging.debug(f"Connected to RTMP. Bitrate: {bitrate}")
                restart_attempts = 0  # Reset on success
            else:
                logging.error("ffmpeg process not running!")
                if restart_attempts < max_restarts:
                    logging.info("Attempting to restart ffmpeg...")
                    streamer.start_stream()
                    restart_attempts += 1
                else:
                    logging.error(
                        "Max ffmpeg restart attempts reached. Exiting or marking unhealthy."
                    )
                    break  # Or set a health flag, or sys.exit(1)
            time.sleep(10)

    # Wait for keyboard interrupt
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        streamer.stop_stream()
        api_client.stop()


if __name__ == "__main__":
    main()
