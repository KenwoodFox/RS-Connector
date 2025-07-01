import os
import subprocess


class Streamer:
    def __init__(self, video_device, robot_id, stream_key, ffmpeg_opts=None):
        self.video_device = video_device
        self.robot_id = robot_id
        self.stream_key = stream_key
        self.ffmpeg_opts = ffmpeg_opts or ""
        self.rtmp_url = (
            f"rtmp://rtmp.robotstreamer.com/live/{self.robot_id}?key={self.stream_key}"
        )

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
        print(f"[Streamer] Running: {cmd}")
        self.proc = subprocess.Popen(cmd, shell=True)

    def stop_stream(self):
        if hasattr(self, "proc"):
            self.proc.terminate()
