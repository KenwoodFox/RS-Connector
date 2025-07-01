# RS-Connector

A simple Dockerized connector for [robotstreamer.com](https://robotstreamer.com) that streams video (from a device or static image) and connects to the robotstreamer.com API.

## Usage

1. Set environment variables (see below)
2. Build and run the Docker container

## Environment Variables
- `VIDEO_DEVICE`: Path to video device (e.g., `/dev/video0`).
- `STREAM_KEY`: Your robotstreamer.com stream key
- `ROBOT_ID`: Robot ID for API
- `API_URL`: (Optional) robotstreamer.com API endpoint
- `FFMPEG_OPTS`: (Optional) Extra ffmpeg options

## Quickstart
```sh
docker build -t rs-connector . --load
docker run --rm \
  -e VIDEO_DEVICE=/dev/video0 \
  -e STREAM_KEY=your_stream_key \
  -e ROBOT_ID=your_robot_id \
  rs-connector
```

## Project Structure
- `rs_connector/streamer.py`: ffmpeg wrapper for streaming
- `rs_connector/api_client.py`: API client for robotstreamer.com
- `rs_connector/main.py`: Entrypoint
- `test_image.jpg`: Optional static image

---

MIT License 