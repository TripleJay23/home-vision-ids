"""
Quick static-image sanity test for FaceRecognizer (Phase 1c-3).

Feeds individual photos to the recognizer and prints the match result.
This is NOT the live pipeline test (that's test_recognition.py, Phase 1c-5)
— this just confirms recognizer.py + face_db.py work correctly in isolation,
before adding tracking/pipeline complexity on top.

IMPORTANT: requires the face DB to already be populated — run
scripts/enroll_face.py first (e.g. `--all`), or this will only report
"no_known_faces" for every image.

Usage:
    python scripts/test_recognizer_static.py path/to/photo1.jpg path/to/photo2.jpg ...

Tip: test with photos NOT used during enrollment (different angle/lighting/
session) — testing against the exact enrolled images only proves the math
works, not that recognition generalizes to a new photo of the same person.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import cv2
from loguru import logger

from engine.core.recognizer import FaceRecognizer


def main():
    parser = argparse.ArgumentParser(description="Static-image sanity test for FaceRecognizer.")
    parser.add_argument("images", nargs="+", help="Path(s) to test image(s)")
    args = parser.parse_args()

    recognizer = FaceRecognizer()

    if recognizer.db.embeddings.size == 0:
        logger.error(
            "Face DB is empty — run `python scripts/enroll_face.py --all` first, "
            "then re-run this test."
        )
        return

    for img_path in args.images:
        frame = cv2.imread(img_path)
        if frame is None:
            logger.error(f"Could not read image: {img_path}")
            continue

        result = recognizer.recognize(frame)
        status = result["status"]

        if status == "recognized":
            logger.success(
                f"{img_path} -> RECOGNIZED as '{result['name']}' "
                f"(distance: {result['distance']:.3f})"
            )
        elif status == "unrecognized":
            logger.warning(
                f"{img_path} -> UNRECOGNIZED (closest distance: {result['distance']:.3f}, "
                f"above threshold)"
            )
        elif status == "no_face":
            logger.warning(f"{img_path} -> NO FACE detected in image")
        else:
            logger.warning(f"{img_path} -> {status}")


if __name__ == "__main__":
    main()