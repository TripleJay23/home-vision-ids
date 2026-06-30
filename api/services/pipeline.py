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
from datetime import datetime
from pathlib import Path

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
        self._paused_jpeg_cache: bytes | None = None        # built once, on demand

        self._running = False
        self._thread: threading.Thread | None = None
        self.fps = 0.0
        self._fps_log_count = 0      # periodic perf-log throttle
        self._recog_ms = 0.0         # last recognition inference time (ms)

        # Live loop runs while this is set; cleared to PAUSE it (during a heavy
        # enrollment build, so YOLO doesn't starve the CPU the build needs).
        self._active = threading.Event()
        self._active.set()

        # Background enrollment: builds run off the request thread on a single
        # worker (sequential, CPU-bound), with per-name status the API exposes so
        # the app can show "enrolling…" → "enrolled" without blocking on the call.
        self._enroll_executor = ThreadPoolExecutor(max_workers=1)
        self._enroll_lock = threading.Lock()
        self._enrollments: dict[str, dict] = {}  # name -> {status, count, error, enrolled_at}

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
        self._enroll_executor.shutdown(wait=False)
        self.stream.stop()
        logger.info("Vision pipeline stopped.")

    def get_jpeg(self) -> bytes | None:
        """Latest annotated frame as JPEG bytes (for the MJPEG stream). None until ready."""
        with self._frame_lock:
            return self._latest_jpeg

    # ── Pause / resume (free the CPU for enrollment) ───────────────────────────

    def pause(self) -> None:
        """Pause the live detection/recognition loop (it idles, publishing a
        placeholder). Used around a heavy enrollment build."""
        self._active.clear()

    def resume(self) -> None:
        """Resume the live loop after a pause."""
        self._active.set()

    # ── Background enrollment ──────────────────────────────────────────────────

    def enroll_async(self, name: str, faces_dir: Path) -> dict:
        """
        Kick off building `name`'s embeddings on the background worker and return
        immediately. The live loop is paused for the duration so the build isn't
        starved by YOLO. Status is tracked per-name (see enrollment_status) so the
        app can poll for completion. Returns the initial status dict.
        """
        with self._enroll_lock:
            self._enrollments[name] = {
                "status": "enrolling", "count": 0, "error": None, "enrolled_at": None,
            }
        self.pause()
        self._enroll_executor.submit(self._run_enrollment, name, faces_dir)
        logger.info(f"Enrollment queued for '{name}' (live loop paused).")
        return self.enrollment_status(name)

    def _run_enrollment(self, name: str, faces_dir: Path) -> None:
        """Worker: build embeddings, persist, reload the recogniser, record status."""
        # Imported here to keep the pipeline's import graph light.
        from engine.core.enrollment import enroll_person
        from engine.core.face_db import FaceDatabase

        try:
            db = FaceDatabase()
            added = enroll_person(name, faces_dir, db, self.detector)
            if added == 0:
                self._set_enrollment(name, "failed", 0,
                                     "No usable face found — re-capture with the face clearer.")
                return
            db.save()
            self.recognizer.reload()  # running pipeline now recognises this member
            self._set_enrollment(name, "enrolled", db.count_for(name), None,
                                 enrolled_at=datetime.now().isoformat(timespec="seconds"))
            logger.success(f"Enrollment complete for '{name}': {db.count_for(name)} embeddings.")
        except Exception as e:
            logger.error(f"Enrollment failed for '{name}': {e}")
            self._set_enrollment(name, "failed", 0, str(e))
        finally:
            # Resume the live loop once no other build is still running.
            with self._enroll_lock:
                still_building = any(v["status"] == "enrolling" for v in self._enrollments.values())
            if not still_building:
                self.resume()
                logger.info("Enrollment(s) done — live loop resumed.")

    def _set_enrollment(self, name: str, status: str, count: int,
                        error: str | None, enrolled_at: str | None = None) -> None:
        with self._enroll_lock:
            self._enrollments[name] = {
                "status": status, "count": count, "error": error, "enrolled_at": enrolled_at,
            }

    def enrollment_status(self, name: str) -> dict | None:
        with self._enroll_lock:
            entry = self._enrollments.get(name)
            return dict(entry) if entry else None

    def enrollments_snapshot(self) -> dict[str, dict]:
        with self._enroll_lock:
            return {k: dict(v) for k, v in self._enrollments.items()}

    def forget_enrollment(self, name: str) -> None:
        """Drop a member's enrollment-status entry (e.g. after deletion)."""
        with self._enroll_lock:
            self._enrollments.pop(name, None)

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        frame_count = 0
        fps_timer = time.time()

        while self._running:
            # Paused during an enrollment build — don't run detection/recognition
            # so the CPU-bound embedding build runs fast. Surface a placeholder so
            # the live view explains the pause instead of freezing.
            if not self._active.is_set():
                self._publish_paused()
                time.sleep(0.15)
                continue

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
            self._signal_lost_jpeg_cache = self._banner_frame("CAMERA SIGNAL LOST", (60, 60, 220))
        return self._signal_lost_jpeg_cache

    def _publish_paused(self) -> None:
        """Publish an 'enrollment in progress' placeholder as the latest frame."""
        with self._frame_lock:
            self._latest_jpeg = self._paused_frame()

    def _paused_frame(self) -> bytes:
        """A frame explaining the live loop is paused for enrollment. Cached."""
        if self._paused_jpeg_cache is None:
            self._paused_jpeg_cache = self._banner_frame("ENROLLING — LIVE PAUSED", (200, 160, 0))
        return self._paused_jpeg_cache

    @staticmethod
    def _banner_frame(text: str, color: tuple[int, int, int]) -> bytes:
        """A black frame with a single centred banner line, encoded to JPEG."""
        w, h = settings.stream_width, settings.stream_height
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        font, fscale, thick = cv2.FONT_HERSHEY_SIMPLEX, 1.4, 3
        (tw, th), _ = cv2.getTextSize(text, font, fscale, thick)
        cv2.putText(
            frame, text, ((w - tw) // 2, (h + th) // 2),
            font, fscale, color, thick, cv2.LINE_AA,
        )
        ok, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes() if ok else b""

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
