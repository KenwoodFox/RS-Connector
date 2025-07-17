import os
import subprocess
import logging
import io
from PIL import Image


class Streamer:
    def __init__(
        self, video_device, robot_id, stream_key, ffmpeg_opts=None, overlay_path=None
    ):
        self.video_device = video_device
        self.robot_id = robot_id
        self.stream_key = stream_key
        self.ffmpeg_opts = ffmpeg_opts or ""
        self.overlay_path = overlay_path
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
        Start ffmpeg for robot jsmpeg video and audio streaming using the provided endpoints.
        video_endpoint: dict with 'host' and 'port'
        audio_endpoint: dict with 'host' and 'port'
        """
        import threading
        import time
        import os

        fifo_path = "/tmp/rs_connector_pipe"
        # Create FIFO if it doesn't exist
        if not os.path.exists(fifo_path):
            os.mkfifo(fifo_path)

        vhost = video_endpoint["host"]
        vport = video_endpoint["port"]
        video_url = f"http://{vhost}:{vport}/{self.stream_key}/{xres}/{yres}/"
        if audio_endpoint:
            ahost = audio_endpoint["host"]
            aport = audio_endpoint["port"]
            audio_url = f"http://{ahost}:{aport}/{self.stream_key}/640/480/"
        else:
            audio_url = video_url  # fallback

        ffmpeg_cmd = (
            f"ffmpeg -f image2pipe -vcodec png -framerate {framerate} -i {fifo_path} "
            f"-c:v mpeg1video -b:v {kbps}k -bf 0 -muxdelay 0.001 -f mpegts {video_url} "
            f"-f lavfi -ac {audio_channels} -i anullsrc=channel_layout=mono:sample_rate={audio_sample_rate} "
            f"-map 0:v -map 1:a -c:a mp2 -b:a {audio_kbps}k -muxdelay 0.01 -f mpegts {audio_url}"
        )
        self.logger.info(
            f"Starting ffmpeg (jsmpeg video+audio, overlay via FIFO): {ffmpeg_cmd}"
        )
        proc = subprocess.Popen(
            ffmpeg_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        def log_ffmpeg_output():
            if self.logger.isEnabledFor(logging.DEBUG):
                for line in proc.stdout:
                    self.logger.debug(f"[ffmpeg] {line.strip()}")
            else:
                for _ in proc.stdout:
                    pass

        threading.Thread(target=log_ffmpeg_output, daemon=True).start()

        def overlay_writer():
            blank_overlay = None
            while True:
                try:
                    # Get base frame
                    if self.video_device.startswith("/dev/video"):
                        import cv2

                        cap = cv2.VideoCapture(self.video_device)
                        ret, frame = cap.read()
                        cap.release()
                        if not ret:
                            self.logger.error(
                                "Failed to capture frame from camera for overlay."
                            )
                            time.sleep(2)
                            continue
                        base = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA))
                    else:
                        base = Image.open(self.video_device).convert("RGBA")
                    # Overlay if present, else blank
                    overlay_img = None
                    if self.overlay_path and os.path.exists(self.overlay_path):
                        try:
                            overlay_img = Image.open(self.overlay_path).convert("RGBA")
                        except Exception as e:
                            self.logger.error(f"Failed to load overlay PNG: {e}")
                    if overlay_img is None:
                        if blank_overlay is None or blank_overlay.size != base.size:
                            blank_overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
                        overlay_img = blank_overlay
                    base.alpha_composite(overlay_img)
                    # Write composited frame to FIFO as PNG
                    buf = io.BytesIO()
                    base.save(buf, format="PNG")
                    with open(fifo_path, "wb") as pipe:
                        pipe.write(buf.getvalue())
                        pipe.flush()
                except BrokenPipeError:
                    self.logger.error(
                        "Broken pipe: ffmpeg process exited, overlay writer stopping."
                    )
                    break
                except Exception as e:
                    self.logger.error(f"Overlay writer error: {e}")
                    break
                time.sleep(2.0)

        threading.Thread(target=overlay_writer, daemon=True).start()

        self.video_proc = proc
        self.audio_proc = proc

        def monitor():
            while True:
                ret = proc.poll()
                if ret is not None:
                    self.logger.error(
                        f"ffmpeg process exited with code {ret}! Restarting..."
                    )
                    proc.terminate()
                    proc.wait()
                    time.sleep(2)
                    self.start_jsmpeg_stream(
                        video_endpoint,
                        xres=xres,
                        yres=yres,
                        framerate=framerate,
                        kbps=kbps,
                        rotation_option=rotation_option,
                        audio_endpoint=audio_endpoint,
                        audio_sample_rate=audio_sample_rate,
                        audio_channels=audio_channels,
                        audio_kbps=audio_kbps,
                    )
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
