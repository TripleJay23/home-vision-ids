"""
Phase 1c-2 / Phase 6 — Face enrollment (pipeline-consistent).

Scans data/faces/<name>/ for images and builds ArcFace embeddings the EXACT
same way the live pipeline does at runtime (full frame → YOLO person box → crop
→ yunet → ArcFace). The actual logic lives in engine/core/enrollment.py so the
CLI and the in-app /members enrollment share one identical implementation.

Usage:
    python scripts/enroll_face.py <name>
    python scripts/enroll_face.py --all      # re-scan all data/faces subfolders

NOTE: first run downloads DeepFace's ArcFace + yunet weights — needs internet
once, cached locally afterward.
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger

from engine.core.face_db import FaceDatabase, PROJECT_ROOT
from engine.core.detector import ObjectDetector
from engine.core.enrollment import enroll_person

KNOWN_FACES_DIR = PROJECT_ROOT / "data" / "faces"


def main():
    parser = argparse.ArgumentParser(
        description="Enroll known faces into the local face DB, through the runtime pipeline."
    )
    parser.add_argument("name", nargs="?", help="Name of person to enroll (folder under data/faces/)")
    parser.add_argument("--all", action="store_true", help="Re-scan and enroll all subfolders under data/faces/")
    args = parser.parse_args()

    if not args.name and not args.all:
        parser.error("Provide a name, or use --all to enroll everyone in data/faces/")

    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
    db = FaceDatabase()
    detector = ObjectDetector()  # load YOLO once, reuse for every image

    names_to_enroll = (
        [d.name for d in KNOWN_FACES_DIR.iterdir() if d.is_dir()]
        if args.all else [args.name]
    )

    if not names_to_enroll:
        logger.warning(f"No subfolders found in {KNOWN_FACES_DIR}")
        return

    total_added = 0
    for name in names_to_enroll:
        logger.info(f"Enrolling '{name}'...")
        total_added += enroll_person(name, KNOWN_FACES_DIR / name, db, detector)

    if total_added > 0:
        db.save()
        logger.success(f"Done. Added {total_added} embedding(s) across {len(names_to_enroll)} folder(s).")
    else:
        logger.warning("No embeddings were added — nothing saved.")


if __name__ == "__main__":
    main()
