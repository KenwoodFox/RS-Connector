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
        self.video_proc = None
        self.audio_proc = None
        self.monitor_thread = None

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
        self.proc = subprocess.Popen(
            cmd,
            shell=True,
        )

    def start_jsmpeg_stream(
        self,
        video_endpoint,
        xres=768,
        yres=432,
        framerate=25,
        kbps=700,
        rotation_option="",
        audio_endpoint=None,
        audio_sample_rate=32000,
        audio_channels=1,
        audio_kbps=64,
    ):
        """
        Start ffmpeg for robot jsmpeg video streaming using the provided endpoint dict.
        video_endpoint: dict with 'host' and 'port'
        audio_endpoint: dict with 'host' and 'port' (optional, for future real audio)
        """
        import threading
        import time

        host = video_endpoint["host"]
        port = video_endpoint["port"]
        url = f"http://{host}:{port}/{self.stream_key}/{xres}/{yres}/"

        def start_video():
            import threading

            if self.video_device.startswith("/dev/video"):
                input_arg = f"-f v4l2 -framerate {framerate} -video_size {xres}x{yres} -r {framerate} -i {self.video_device} {rotation_option}"
            else:
                input_arg = f"-loop 1 -framerate {framerate} -video_size {xres}x{yres} -i {self.video_device}"
            video_args = f"-c:v mpeg1video -b:v {kbps}k -bf 0 -muxdelay 0.001"
            cmd = f"ffmpeg {input_arg} {video_args} -f mpegts {url}"
            self.logger.info(f"Starting ffmpeg (jsmpeg video): {cmd}")
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            def log_ffmpeg_output():
                if self.logger.isEnabledFor(logging.DEBUG):
                    for line in proc.stdout:
                        self.logger.debug(f"[ffmpeg video] {line.strip()}")
                else:
                    for _ in proc.stdout:
                        pass  # discard output

            threading.Thread(target=log_ffmpeg_output, daemon=True).start()
            return proc

        def start_audio():
            import threading

            # For now, always use sine tone
            if audio_endpoint:
                audio_host = audio_endpoint["host"]
                audio_port = audio_endpoint["port"]
                audio_url = (
                    f"http://{audio_host}:{audio_port}/{self.stream_key}/640/480/"
                )
            else:
                audio_url = url  # fallback for testing
            input_arg = f"-f lavfi -ac {audio_channels} -i anullsrc=channel_layout=mono:sample_rate={audio_sample_rate}"
            audio_args = f"-c:a mp2 -b:a {audio_kbps}k -muxdelay 0.01"
            cmd = f"ffmpeg {input_arg} {audio_args} -f mpegts {audio_url}"
            self.logger.info(f"Starting ffmpeg (jsmpeg audio): {cmd}")
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            def log_ffmpeg_output():
                if self.logger.isEnabledFor(logging.DEBUG):
                    for line in proc.stdout:
                        self.logger.debug(f"[ffmpeg audio] {line.strip()}")
                else:
                    for _ in proc.stdout:
                        pass  # discard output

            threading.Thread(target=log_ffmpeg_output, daemon=True).start()
            return proc

        def monitor():
            while True:
                self.video_proc = start_video()
                self.audio_proc = start_audio()

                while True:
                    v_ret = self.video_proc.poll()
                    a_ret = self.audio_proc.poll()
                    if v_ret is not None or a_ret is not None:
                        self.logger.error(
                            "ffmpeg video or audio process not running! Restarting both..."
                        )
                        self.video_proc.terminate()
                        self.audio_proc.terminate()
                        self.video_proc.wait()
                        self.audio_proc.wait()
                        time.sleep(2)
                        break
                    time.sleep(1)

        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    def stop_stream(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            self.logger.info("Stopped ffmpeg process.")

    def get_bitrate(self):
        # Stub: In a real implementation, parse ffmpeg logs or use ffprobe
        return None
