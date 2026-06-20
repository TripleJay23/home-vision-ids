"""
Phase 1c-1 — YOLOv8n + ByteTrack tracking test.

Runs the live camera stream through YOLOv8n with persistent tracking
and draws bounding boxes + stable track IDs on detected persons, pets,
and objects in real time.

This verifies two things before moving to 1c-2 (face enrollment):
    1. track_id stays consistent for a person as they move across frames.
    2. FPS doesn't drop meaningfully from the 1b baseline (14-17 FPS).

Usage:
    python scripts/test_tracking.py

Press Q to quit.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import time
from loguru import logger
from engine.utils.stream import VideoStream
from engine.core.detector import ObjectDetector


# Colour per label (BGR)
LABEL_COLORS = {
    "person":   (0, 255, 0),     # green
    "cat":      (255, 165, 0),   # orange
    "dog":      (255, 165, 0),   # orange
    "backpack": (0, 200, 255),   # yellow
    "handbag":  (0, 200, 255),   # yellow
    "suitcase": (0, 200, 255),   # yellow
}
DEFAULT_COLOR = (200, 200, 200)  # grey for anything else


def draw_detections(frame, detections: list[dict]) -> None:
    """Draw bounding boxes, labels, and track IDs onto the frame in-place."""
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        label = det["label"]
        conf  = det["confidence"]
        track_id = det.get("track_id")
        color = LABEL_COLORS.get(label, DEFAULT_COLOR)

        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Label text — include track ID (or "?" if not yet assigned)
        id_str = f"#{track_id}" if track_id is not None else "#?"
        text = f"{label} {id_str} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)


def main():
    logger.info("Phase 1c-1 — Tracking test starting...")

    # ── Start stream ─────────────────────────────────────────
    stream = VideoStream()
    try:
        stream.start()
    except ConnectionError as e:
        logger.error(str(e))
        return

    # ── Load detector ────────────────────────────────────────
    logger.info("Loading YOLOv8n model...")
    detector = ObjectDetector()
    logger.success("Model loaded. Starting tracking loop...")

    # ── FPS tracking ─────────────────────────────────────────
    fps = 0
    frame_count = 0
    fps_timer = time.time()

    # ── Track ID bookkeeping (for sanity-checking stability) ──
    seen_track_ids = set()

    while True:
        frame = stream.read()
        if frame is None:
            continue

        # ── Run detection + tracking ───────────────────────────
        detections = detector.track(frame)

        # ── Draw results ──────────────────────────────────────
        draw_detections(frame, detections)

        # ── FPS overlay ───────────────────────────────────────
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
            f"Unique IDs seen: {len(seen_track_ids)}  |  Q to quit",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2,
        )

        cv2.imshow("Home Vision IDS — Tracking Test", frame)

        # ── Log detections to terminal ─────────────────────────
        new_ids = {d["track_id"] for d in detections if d.get("track_id") is not None}
        if new_ids - seen_track_ids:
            logger.info(f"New track ID(s) assigned: {new_ids - seen_track_ids}")
        seen_track_ids |= new_ids

        if detections:
            summary = [f"{d['label']}#{d.get('track_id', '?')}" for d in detections]
            logger.info(f"Tracked: {summary}  |  FPS: {fps:.1f}")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("Quit signal received.")
            break

    stream.stop()
    cv2.destroyAllWindows()
    logger.success(
        f"Tracking test complete. Total unique track IDs seen: {len(seen_track_ids)}"
    )


if __name__ == "__main__":
    main()