import os
import subprocess
import logging


class Streamer:
    def __init__(self, video_device, robot_id, stream_key, ffmpeg_opts=None):
        self.video_device = video_device
        self.robot_id = robot_id
        self.stream_key = stream_key
        self.ffmpeg_opts = ffmpeg_opts or ""
        self.rtmp_url = (
            f"rtmp://rtmp.robotstreamer.com/live/{self.robot_id}?key={self.stream_key}"
        )
        self.proc = None
        self.logger = logging.getLogger("Streamer")

    def start_stream(self):
        # If it's a video device (e.g., /dev/video0)
        if self.video_device.startswith("/dev/video"):
            input_arg = f"-f v4l2 -i {self.video_device}"
        else:
            # Static image: loop the image as video
            input_arg = f"-loop 1 -framerate 2 -i {self.video_device}"
        cmd = (
            f"ffmpeg {input_arg} {self.ffmpeg_opts} -c:v libx264 -f flv {self.rtmp_url}"
        )
        self.logger.info(f"Starting ffmpeg: {cmd}")
        # Suppress ffmpeg output unless error
        self.proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def stop_stream(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            self.logger.info("Stopped ffmpeg process.")

    def is_running(self):
        return self.proc and self.proc.poll() is None

    def get_bitrate(self):
        # Stub: In a real implementation, parse ffmpeg logs or use ffprobe
        return None
