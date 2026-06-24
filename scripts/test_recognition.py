"""
Phase 1c-5 — Live recognition pipeline integration test.

Wires together the full 1c stack:
    VideoStream → detector.track() → TrackStateManager
    → (threaded) FaceRecognizer → overlay labels on live stream

Recognition runs in a background thread pool so DeepFace inference
never blocks the detection loop. The main loop stays at detection FPS;
recognition results arrive asynchronously and get picked up on the next
frame once the thread resolves.

Usage:
    python scripts/test_recognition.py

Press Q to quit.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from config.settings import settings
from engine.utils.stream import VideoStream
from engine.core.detector import ObjectDetector
from engine.core.recognizer import FaceRecognizer
from engine.core.track_state import TrackStateManager

# Only crop from the top portion of a person's bounding box for face extraction.
# A full-body crop wastes time giving DeepFace/yunet a tiny face in a large frame.
# 0.45 = top 45% of the box — covers face + neck comfortably even for tall frames.
FACE_CROP_RATIO = 0.45

# Minimum person bounding box height before attempting recognition comes from
# settings (MIN_PERSON_BOX_HEIGHT) — shared with the real pipeline so this debug
# tool behaves identically. Below it the face is too small for yunet; lower the
# setting to recognise people further from the camera.
MIN_PERSON_BOX_HEIGHT = settings.min_person_box_height

# Thread pool size: 1 worker keeps recognition truly sequential and prevents
# multiple heavy DeepFace calls competing for CPU at once. Raise to 2 if a
# multi-person scene ever causes a backlog — but start conservative.
MAX_RECOGNITION_WORKERS = 1

# Colour per label (BGR)
LABEL_COLORS = {
    "person":   (0, 255, 0),
    "cat":      (255, 165, 0),
    "dog":      (255, 165, 0),
    "backpack": (0, 200, 255),
    "handbag":  (0, 200, 255),
    "suitcase": (0, 200, 255),
}
DEFAULT_COLOR = (200, 200, 200)

# Recognized / unrecognized person label colors
KNOWN_COLOR   = (0, 255, 128)   # green-ish
STRANGER_COLOR = (0, 80, 255)   # red-ish
PENDING_COLOR  = (200, 200, 0)  # yellow-ish


def extract_face_crop(frame: "np.ndarray", bbox: list[float]) -> "np.ndarray":
    """Crop the upper portion of a person bounding box for face recognition."""
    x1, y1, x2, y2 = [int(v) for v in bbox]
    face_h = int((y2 - y1) * FACE_CROP_RATIO)
    # Clamp to frame bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1], x2)
    y2 = min(frame.shape[0], y1 + face_h)
    return frame[y1:y2, x1:x2].copy()


def draw_detection(frame, det: dict, label: str) -> None:
    """Draw bounding box + recognition label for one detection."""
    x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
    det_label = det["label"]
    conf = det["confidence"]
    track_id = det.get("track_id")

    # Box color: person boxes vary by recognition status, others use label color
    if det_label == "person":
        if "stranger" in label:
            color = STRANGER_COLOR
        elif "identifying" in label:
            color = PENDING_COLOR
        else:
            color = KNOWN_COLOR
    else:
        color = LABEL_COLORS.get(det_label, DEFAULT_COLOR)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # Top label: name/status for persons, class label for objects
    if det_label == "person":
        id_str = f"#{track_id}" if track_id is not None else "#?"
        text = f"{label} {id_str}"
    else:
        text = f"{det_label} {conf:.0%}"

    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
    cv2.putText(frame, text, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)


def main():
    logger.info("Phase 1c-5 — Live recognition pipeline starting...")

    stream = VideoStream()
    try:
        stream.start()
    except ConnectionError as e:
        logger.error(str(e))
        return

    detector = ObjectDetector()
    recognizer = FaceRecognizer()
    state_manager = TrackStateManager()

    # Lock protects state_manager.update_result() calls from recognition threads
    state_lock = threading.Lock()

    executor = ThreadPoolExecutor(max_workers=MAX_RECOGNITION_WORKERS)

    fps = 0
    frame_count = 0
    fps_timer = time.time()

    logger.success("Pipeline ready. Starting live recognition loop...")

    while True:
        frame = stream.read()
        if frame is None:
            continue

        detections = detector.track(frame)

        # ── Track state housekeeping ──────────────────────────────────────
        active_ids = {
            d["track_id"] for d in detections
            if d["track_id"] is not None
        }
        with state_lock:
            state_manager.evict_stale(active_ids)

        # ── Per-detection: update state + maybe submit recognition ────────
        for det in detections:
            track_id = det.get("track_id")
            if track_id is None or det["label"] != "person":
                continue

            with state_lock:
                state_manager.update_seen(track_id)
                should_run = state_manager.should_recognize(track_id)
                if should_run:
                    state_manager.mark_in_flight(track_id)

            if should_run:
                x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
                box_height = y2 - y1
                if box_height < MIN_PERSON_BOX_HEIGHT:
                    # Person too far — face crop will be too small for yunet.
                    # Release in-flight so should_recognize() fires again once
                    # they move closer, but don't spam retries.
                    with state_lock:
                        state_manager.update_result(
                            track_id, {"status": "no_face", "name": None, "distance": None}
                        )
                    continue

                crop = extract_face_crop(frame, det["bbox"])
                if crop.size == 0:
                    with state_lock:
                        state_manager.update_result(
                            track_id, {"status": "no_face", "name": None, "distance": None}
                        )
                    continue

                # Capture track_id for closure
                _tid = track_id
                future = executor.submit(recognizer.recognize, crop)

                def on_done(f, tid=_tid):
                    try:
                        result = f.result()
                    except Exception as e:
                        logger.warning(f"Recognition thread error for track #{tid}: {e}")
                        result = {"status": "no_face", "name": None, "distance": None}
                    with state_lock:
                        state_manager.update_result(tid, result)
                future.add_done_callback(on_done)

        # ── Draw ──────────────────────────────────────────────────────────
        for det in detections:
            track_id = det.get("track_id")
            if det["label"] == "person" and track_id is not None:
                with state_lock:
                    label = state_manager.get_label(track_id)
            else:
                label = det["label"]
            draw_detection(frame, det, label)

        # ── FPS overlay ───────────────────────────────────────────────────
        frame_count += 1
        elapsed = time.time() - fps_timer
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            frame_count = 0
            fps_timer = time.time()

        person_count = sum(1 for d in detections if d["label"] == "person")
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}  |  Persons: {person_count}  |  "
            f"Active tracks: {state_manager.active_count}  |  Q to quit",
            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
        )

        cv2.imshow("Home Vision IDS — Recognition", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("Quit signal received.")
            break

    executor.shutdown(wait=False)
    stream.stop()
    cv2.destroyAllWindows()
    logger.success("Recognition pipeline test complete.")


if __name__ == "__main__":
    main()