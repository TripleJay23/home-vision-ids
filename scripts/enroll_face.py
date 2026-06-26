"""
Phase 1c-2 / Phase 6 — Face enrollment (pipeline-consistent).

Scans data/faces/<name>/ for images and builds ArcFace embeddings the EXACT
same way the live pipeline does at runtime:

    full frame → YOLO person box → crop top portion → yunet → ArcFace

WHY mirror the runtime path: if enrollment used a different face detector /
alignment or different framing than runtime, the same person would land in a
slightly different embedding space — smearing cosine distances and letting
strangers match known people (observed live 2026-06-26 before this change).
Enrolling through the runtime path keeps enrolled embeddings and live query
embeddings directly comparable. The crop and the embedding are produced by the
same shared helpers the pipeline uses (engine/utils/face_crop.extract_face_crop
and engine/core/recognizer.extract_embedding).

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

import cv2
from loguru import logger

from engine.core.face_db import FaceDatabase, PROJECT_ROOT
from engine.core.detector import ObjectDetector
from engine.core.recognizer import extract_embedding
from engine.utils.face_crop import extract_face_crop

KNOWN_FACES_DIR = PROJECT_ROOT / "data" / "faces"
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def enroll_person(name: str, db: FaceDatabase, detector: ObjectDetector) -> int:
    """
    Enroll all images in data/faces/<name>/, building embeddings through the
    runtime pipeline (YOLO person-crop → yunet → ArcFace). Replaces any existing
    embeddings for this person first, so re-running always reflects exactly
    what's in their folder. Returns count of embeddings added.
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
    skipped = 0
    for img_path in images:
        frame = cv2.imread(str(img_path))
        if frame is None:
            logger.warning(f"Could not read {img_path.name}, skipping.")
            skipped += 1
            continue

        # 1. Find the person (YOLO), exactly like the live pipeline.
        persons = [d for d in detector.detect(frame) if d["label"] == "person"]
        if not persons:
            logger.warning(f"No person detected in {img_path.name}, skipping.")
            skipped += 1
            continue

        # 2. Largest person box = the subject; crop the top portion (same helper).
        det = max(persons, key=lambda d: d["bbox"][3] - d["bbox"][1])
        crop = extract_face_crop(frame, det["bbox"])

        # 3. Embed via the SAME function runtime uses (yunet + ArcFace).
        embedding = extract_embedding(crop)
        if embedding is None:
            logger.warning(f"No face found in the person-crop of {img_path.name}, skipping.")
            skipped += 1
            continue

        db.add_embedding(name, embedding.tolist(), source_image=img_path.name)
        added += 1
        logger.info(f"Enrolled: {img_path.name}")

    logger.info(f"'{name}': {added} enrolled, {skipped} skipped (no person/face in crop).")
    if added == 0 and removed:
        logger.error(
            f"'{name}' had {removed} old embedding(s) removed but 0 new ones added — "
            f"they will have NO embeddings once saved! Check the images in {person_dir}."
        )

    return added


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
        total_added += enroll_person(name, db, detector)

    if total_added > 0:
        db.save()
        logger.success(f"Done. Added {total_added} embedding(s) across {len(names_to_enroll)} folder(s).")
    else:
        logger.warning("No embeddings were added — nothing saved.")


if __name__ == "__main__":
    main()
