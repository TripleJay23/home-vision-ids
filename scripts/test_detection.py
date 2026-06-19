"""
Phase 1b — YOLOv8n detection test.

Runs the live camera stream through YOLOv8n and draws bounding boxes
on detected persons, pets, and objects in real time.

Usage:
    python scripts/test_detection.py

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
    """Draw bounding boxes and labels onto the frame in-place."""
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        label = det["label"]
        conf  = det["confidence"]
        color = LABEL_COLORS.get(label, DEFAULT_COLOR)

        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Label background
        text = f"{label} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)

        # Label text
        cv2.putText(frame, text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)


def main():
    logger.info("Phase 1b — YOLOv8n detection test starting...")

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
    logger.success("Model loaded. Starting detection loop...")

    # ── FPS tracking ─────────────────────────────────────────
    fps = 0
    frame_count = 0
    fps_timer = time.time()

    while True:
        frame = stream.read()
        if frame is None:
            continue

        # ── Run detection ─────────────────────────────────────
        detections = detector.detect(frame)

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
            f"FPS: {fps:.1f}  |  Persons: {person_count}  |  Q to quit",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2,
        )

        cv2.imshow("Home Vision IDS — Detection Test", frame)

        # ── Log detections to terminal ─────────────────────────
        if detections:
            labels = [d["label"] for d in detections]
            logger.info(f"Detected: {labels}  |  FPS: {fps:.1f}")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("Quit signal received.")
            break

    stream.stop()
    cv2.destroyAllWindows()
    logger.success("Detection test complete.")


if __name__ == "__main__":
    main()