"""
Phase 1a — Stream connection test.

Run this to verify your Pixel 4a stream is readable before
plugging it into the full engine.

Usage:
    python scripts/test_stream.py

Press Q to quit the preview window.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
from loguru import logger
from engine.utils.stream import VideoStream


def main():
    logger.info("Starting stream test — press Q in the preview window to quit.")

    stream = VideoStream()

    try:
        stream.start()
    except ConnectionError as e:
        logger.error(str(e))
        logger.info("Check that:")
        logger.info("  1. IP Webcam app is running on your Pixel 4a")
        logger.info("  2. Your laptop and Pixel 4a are on the same WiFi")
        logger.info("  3. CAMERA_URL in .env matches the IP shown in the app")
        return

    logger.success("Stream connected! Opening preview window...")
    frame_count = 0

    while True:
        frame = stream.read()

        if frame is None:
            continue

        frame_count += 1

        # Overlay frame counter on the preview
        cv2.putText(
            frame,
            f"Home Vision IDS | Frame {frame_count} | Press Q to quit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

        cv2.imshow("Home Vision IDS — Stream Test", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("Quit signal received.")
            break

    stream.stop()
    cv2.destroyAllWindows()
    logger.success(f"Test complete. Total frames captured: {frame_count}")


if __name__ == "__main__":
    main()