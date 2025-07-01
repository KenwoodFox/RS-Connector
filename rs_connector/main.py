import os
import time
from .streamer import Streamer
from .api_client import APIClient


def main():
    video_device = os.environ.get("VIDEO_DEVICE", "rs_connector/test_pattern.jpg")
    stream_key = os.environ.get("STREAM_KEY", "")
    robot_id = os.environ.get("ROBOT_ID")
    api_url = os.environ.get("API_URL")
    ffmpeg_opts = os.environ.get("FFMPEG_OPTS", "")

    if not stream_key:
        print("[main] STREAM_KEY not set. Exiting.")
        return
    if not robot_id:
        print("[main] ROBOT_ID not set. Exiting.")
        return

    streamer = Streamer(video_device, robot_id, stream_key, ffmpeg_opts)
    api_client = APIClient(api_url, robot_id)

    try:
        streamer.start_stream()
        while True:
            # Example: post status every 10 seconds
            api_client.post_status({"status": "online"})
            time.sleep(10)
    except KeyboardInterrupt:
        print("[main] Shutting down...")
    finally:
        streamer.stop_stream()


if __name__ == "__main__":
    main()
