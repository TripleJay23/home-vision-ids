"""
Phase 2 — Vision pipeline service.

The headless, long-running version of the live loop previously prototyped in
scripts/test_recognition.py. It owns the full stack and runs in a background
thread so it never blocks the async FastAPI event loop:

    VideoStream → detector.track() → TrackStateManager
        → (threaded) FaceRecognizer → AlertService on confirmed strangers
        → annotated JPEG published for the MJPEG /stream endpoint

Lifecycle is owned by the API: build_pipeline() is called once in the FastAPI
lifespan startup (so the heavy models load exactly once, never per-request),
and stop() in shutdown. get_jpeg() feeds the streaming route.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from loguru import logger

from config.settings import settings
from engine.utils.stream import VideoStream
from engine.core.detector import ObjectDetector
from engine.core.recognizer import FaceRecognizer
from engine.core.track_state import TrackStateManager
from engine.core.alerter import build_alert_service
from engine.utils.face_crop import extract_face_crop

# Min person bbox height to attempt recognition comes from settings
# (MIN_PERSON_BOX_HEIGHT) so it can be tuned per room without a code change —
# lower it to recognise people further from a top-corner camera.

# One recognition worker keeps heavy DeepFace calls sequential (CPU-bound).
MAX_RECOGNITION_WORKERS = 1

# Box colours (BGR) by recognition status.
KNOWN_COLOR = (0, 255, 128)
STRANGER_COLOR = (0, 80, 255)
PENDING_COLOR = (200, 200, 0)


class VisionPipeline:
    """Owns the live detection/recognition/alert loop in a background thread."""

    def __init__(self):
        self.stream = VideoStream()
        self.detector = ObjectDetector()
        self.recognizer = FaceRecognizer()
        self.state = TrackStateManager()
        self.alerter = build_alert_service()

        self._executor = ThreadPoolExecutor(max_workers=MAX_RECOGNITION_WORKERS)
        self._state_lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._signal_lost_jpeg_cache: bytes | None = None  # built once, on demand

        self._running = False
        self._thread: threading.Thread | None = None
        self.fps = 0.0
        self._fps_log_count = 0      # periodic perf-log throttle
        self._recog_ms = 0.0         # last recognition inference time (ms)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Connect the stream and launch the background loop. Raises on stream failure."""
        self.stream.start()  # ConnectionError if the camera is unreachable
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="vision-pipeline")
        self._thread.start()
        logger.success("Vision pipeline started.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._executor.shutdown(wait=False)
        self.stream.stop()
        logger.info("Vision pipeline stopped.")

    def get_jpeg(self) -> bytes | None:
        """Latest annotated frame as JPEG bytes (for the MJPEG stream). None until ready."""
        with self._frame_lock:
            return self._latest_jpeg

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        frame_count = 0
        fps_timer = time.time()

        while self._running:
            frame = self.stream.read()
            if frame is None:
                # Camera down or no frame yet — surface a "signal lost" frame so
                # the live view shows the loss instead of freezing on the last
                # good frame. Sleep to avoid spinning while the feed is dead.
                self._publish_signal_lost()
                time.sleep(0.2)
                continue

            detections = self.detector.track(frame)

            # Drop tracks only after a grace period (not on the first missing
            # frame), so detector flicker doesn't reset recognition state.
            with self._state_lock:
                evicted = self.state.evict_expired()
            for tid in evicted:
                self.alerter.forget(tid)

            for det in detections:
                track_id = det.get("track_id")
                if track_id is None or det["label"] != "person":
                    continue
                self._maybe_recognize(track_id, det, frame)
                self._maybe_alert(track_id, det, frame)

            self._publish(frame, detections)

            frame_count += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                self.fps = frame_count / elapsed
                frame_count = 0
                fps_timer = time.time()
                # Periodic performance insight (~every 5s) for tuning model size.
                self._fps_log_count += 1
                if self._fps_log_count >= 5:
                    self._fps_log_count = 0
                    logger.info(
                        f"[perf] FPS {self.fps:.1f} | active tracks {self.state.active_count} "
                        f"| last recog {self._recog_ms:.0f}ms"
                    )

    # ── Per-track steps ──────────────────────────────────────────────────────

    def _maybe_recognize(self, track_id: int, det: dict, frame: np.ndarray) -> None:
        """Submit a recognition job for this track if the state machine says it's due."""
        with self._state_lock:
            self.state.update_seen(track_id)
            should_run = self.state.should_recognize(track_id)
            if should_run:
                self.state.mark_in_flight(track_id)
        if not should_run:
            return

        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        if (y2 - y1) < settings.min_person_box_height:
            # Too far for a usable face crop — release in-flight, retry later.
            with self._state_lock:
                self.state.update_result(track_id, {"status": "no_face", "name": None, "distance": None})
            return

        crop = extract_face_crop(frame, det["bbox"])
        if crop.size == 0:
            with self._state_lock:
                self.state.update_result(track_id, {"status": "no_face", "name": None, "distance": None})
            return

        def _timed_recognize(c):
            t = time.time()
            try:
                return self.recognizer.recognize(c)
            finally:
                self._recog_ms = (time.time() - t) * 1000.0

        future = self._executor.submit(_timed_recognize, crop)

        def on_done(f, tid=track_id):
            try:
                result = f.result()
            except Exception as e:
                logger.warning(f"Recognition thread error for track #{tid}: {e}")
                result = {"status": "no_face", "name": None, "distance": None}
            with self._state_lock:
                self.state.update_result(tid, result)

        future.add_done_callback(on_done)

    def _maybe_alert(self, track_id: int, det: dict, frame: np.ndarray) -> None:
        """Raise an alert if recognition has settled this track as a stranger."""
        with self._state_lock:
            status, distance = self.state.status_and_distance(track_id)
        if status == "unrecognized":
            # AlertService enforces the per-track cooldown, so calling every
            # frame a stranger is visible is safe — it dedupes internally.
            self.alerter.handle_unknown(track_id, frame, det["bbox"], distance)

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _publish(self, frame: np.ndarray, detections: list[dict]) -> None:
        """Annotate the frame and store it as JPEG for the stream endpoint."""
        for det in detections:
            track_id = det.get("track_id")
            if det["label"] == "person" and track_id is not None:
                with self._state_lock:
                    label = self.state.get_label(track_id)
            else:
                label = det["label"]
            self._draw(frame, det, label)

        cv2.putText(
            frame, f"FPS: {self.fps:.1f}  |  tracks: {self.state.active_count}",
            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
        )

        ok, buf = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.stream_jpeg_quality]
        )
        if ok:
            with self._frame_lock:
                self._latest_jpeg = buf.tobytes()

    def _publish_signal_lost(self) -> None:
        """Publish a 'camera signal lost' placeholder as the latest frame."""
        with self._frame_lock:
            self._latest_jpeg = self._signal_lost_frame()

    def _signal_lost_frame(self) -> bytes:
        """A black frame with a 'CAMERA SIGNAL LOST' banner. Built once, cached."""
        if self._signal_lost_jpeg_cache is None:
            w, h = settings.stream_width, settings.stream_height
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            text = "CAMERA SIGNAL LOST"
            font, fscale, thick = cv2.FONT_HERSHEY_SIMPLEX, 1.4, 3
            (tw, th), _ = cv2.getTextSize(text, font, fscale, thick)
            cv2.putText(
                frame, text, ((w - tw) // 2, (h + th) // 2),
                font, fscale, (60, 60, 220), thick, cv2.LINE_AA,
            )
            ok, buf = cv2.imencode(".jpg", frame)
            self._signal_lost_jpeg_cache = buf.tobytes() if ok else b""
        return self._signal_lost_jpeg_cache

    @staticmethod
    def _draw(frame: np.ndarray, det: dict, label: str) -> None:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        if det["label"] == "person":
            if "stranger" in label:
                color = STRANGER_COLOR
            elif "identifying" in label:
                color = PENDING_COLOR
            else:
                color = KNOWN_COLOR
            track_id = det.get("track_id")
            text = f"{label} #{track_id}" if track_id is not None else label
        else:
            color = (200, 200, 200)
            text = f"{det['label']} {det['confidence']:.0%}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, text, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)


# Module-level singleton — built once at API startup, shared by all routes.
_pipeline: VisionPipeline | None = None


def build_pipeline() -> VisionPipeline:
    """Create the shared pipeline instance (loads models once). Idempotent."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VisionPipeline()
    return _pipeline


def get_pipeline() -> VisionPipeline | None:
    """Return the shared pipeline, or None if it hasn't been built yet."""
    return _pipeline
