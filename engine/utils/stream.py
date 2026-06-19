import cv2
import threading
import time
from loguru import logger

from config.settings import settings


class VideoStream:
    """
    Reads frames from an MJPEG/RTSP camera stream in a background thread.

    Using a dedicated thread means the main engine loop always gets
    the LATEST frame without waiting for the camera — no frame queue
    buildup, no lag. Drop-in replaceable with any URL OpenCV supports.

    Usage:
        stream = VideoStream()
        stream.start()
        frame = stream.read()
        stream.stop()
    """

    def __init__(self, url: str = None):
        self.url = url or settings.camera_url
        self.cap = None
        self.frame = None
        self.running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        """Connect to the stream and start the background reader thread."""
        logger.info(f"Connecting to camera stream: {self.url}")
        self.cap = cv2.VideoCapture(self.url)

        if not self.cap.isOpened():
            logger.error(f"Failed to connect to stream: {self.url}")
            raise ConnectionError(f"Cannot open camera stream at {self.url}")

        # Set frame size to match settings
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.stream_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.stream_height)

        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.success(f"Stream connected. Resolution: {settings.stream_width}x{settings.stream_height}")
        return self

    def _read_loop(self):
        """Background thread — continuously reads and stores the latest frame."""
        consecutive_failures = 0

        while self.running:
            ret, frame = self.cap.read()

            if ret:
                with self._lock:
                    self.frame = frame
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Frame read failed ({consecutive_failures} in a row)")

                if consecutive_failures >= 10:
                    logger.error("Stream lost. Attempting reconnect in 3 seconds...")
                    time.sleep(3)
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.url)
                    consecutive_failures = 0

    def read(self):
        """Return the latest frame. Returns None if no frame available yet."""
        with self._lock:
            return self.frame.copy() if self.frame is not None else None

    def is_connected(self) -> bool:
        return self.running and self.frame is not None

    def stop(self):
        """Stop the background thread and release the camera."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        logger.info("Camera stream stopped.")