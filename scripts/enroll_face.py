"""
Phase 1c-2 — Face enrollment script.

Scans data/faces/<name>/ for images, generates an ArcFace embedding
for each detected face, and adds them to the local face database.

Usage:
    python scripts/enroll_face.py <name>
    python scripts/enroll_face.py --all      # re-scan all data/faces subfolders

Setup: create data/faces/<name>/ and drop in 3-5+ clear photos of that
person (different angles/lighting improves accuracy). Then run this script.

NOTE: first run downloads DeepFace's RetinaFace + ArcFace model weights —
requires internet access once, cached locally afterward.
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deepface import DeepFace
from loguru import logger

from engine.core.face_db import FaceDatabase, PROJECT_ROOT

KNOWN_FACES_DIR = PROJECT_ROOT / "data" / "faces"
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Heavier, more accurate detector backend — fine here since enrollment is
# offline/one-time. The live pipeline (1c-3 recognizer) will use a lighter
# backend instead, since that one runs in the real-time loop.
ENROLLMENT_DETECTOR_BACKEND = "retinaface"
EMBEDDING_MODEL = "ArcFace"


def enroll_person(name: str, db: FaceDatabase) -> int:
    """
    Enroll all images in data/faces/<name>/. Replaces any existing embeddings
    for this person first, so re-running enrollment always reflects exactly
    what's currently in their folder — not appended on top of old data.
    Returns count of embeddings added.
    """
    person_dir = KNOWN_FACES_DIR / name
    if not person_dir.exists():
        logger.error(f"No folder found at {person_dir}")
        return 0

    images = [f for f in person_dir.iterdir() if f.suffix.lower() in VALID_EXTENSIONS]
    if not images:
        logger.warning(f"No images found in {person_dir}")
        return 0

    removed = db.remove_person(name)
    if removed:
        logger.info(f"Cleared {removed} existing embedding(s) for '{name}' before re-enrolling.")

    added = 0
    for img_path in images:
        try:
            results = DeepFace.represent(
                img_path=str(img_path),
                model_name=EMBEDDING_MODEL,
                detector_backend=ENROLLMENT_DETECTOR_BACKEND,
                enforce_detection=True,
            )
        except ValueError as e:
            # DeepFace raises ValueError when no face is detected
            logger.warning(f"No face detected in {img_path.name}, skipping: {e}")
            continue

        if len(results) > 1:
            logger.warning(
                f"{img_path.name}: {len(results)} faces detected, "
                f"using the largest (most prominent) face only."
            )
            results = [max(results, key=lambda r: r["facial_area"]["w"] * r["facial_area"]["h"])]

        embedding = results[0]["embedding"]
        db.add_embedding(name, embedding, source_image=img_path.name)
        added += 1
        logger.info(f"Enrolled: {img_path.name}")

    if added == 0 and removed:
        logger.error(
            f"'{name}' had {removed} old embedding(s) removed but 0 new ones added — "
            f"they will have NO embeddings once saved! Check the images in {person_dir}."
        )

    return added


def main():
    parser = argparse.ArgumentParser(description="Enroll known faces into the local face DB.")
    parser.add_argument("name", nargs="?", help="Name of person to enroll (folder under data/faces/)")
    parser.add_argument("--all", action="store_true", help="Re-scan and enroll all subfolders under data/faces/")
    args = parser.parse_args()

    if not args.name and not args.all:
        parser.error("Provide a name, or use --all to enroll everyone in data/faces/")

    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
    db = FaceDatabase()

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
        total_added += enroll_person(name, db)

    if total_added > 0:
        db.save()
        logger.success(f"Done. Added {total_added} embedding(s) across {len(names_to_enroll)} folder(s).")
    else:
        logger.warning("No embeddings were added — nothing saved.")


if __name__ == "__main__":
    main()