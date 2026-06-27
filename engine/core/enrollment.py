"""
Shared enrollment logic.

Builds ArcFace embeddings for a person from the images in their folder, through
the EXACT same path the live pipeline uses at runtime:

    image → YOLO person box → crop top portion → yunet → ArcFace

Used by BOTH scripts/enroll_face.py (CLI) and the /members API (in-app
enrollment), so every enrollment path is identical and comparable to runtime.
See the Phase 6 note in docs/development_journal.md for why this matters.
"""

from __future__ import annotations

from pathlib import Path

import cv2
from loguru import logger

from engine.core.detector import ObjectDetector
from engine.core.face_db import FaceDatabase
from engine.core.recognizer import extract_embedding
from engine.utils.face_crop import extract_face_crop

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def enroll_person(name: str, person_dir: Path, db: FaceDatabase, detector: ObjectDetector) -> int:
    """
    Enroll every image in `person_dir` into `db` under `name`, building each
    embedding through the runtime pipeline (YOLO crop → yunet → ArcFace).
    Replaces any existing embeddings for `name` first. Returns count added.
    Caller is responsible for db.save().
    """
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

        persons = [d for d in detector.detect(frame) if d["label"] == "person"]
        if not persons:
            logger.warning(f"No person detected in {img_path.name}, skipping.")
            skipped += 1
            continue

        det = max(persons, key=lambda d: d["bbox"][3] - d["bbox"][1])
        crop = extract_face_crop(frame, det["bbox"])

        embedding = extract_embedding(crop)
        if embedding is None:
            logger.warning(f"No face found in the person-crop of {img_path.name}, skipping.")
            skipped += 1
            continue

        db.add_embedding(name, embedding.tolist(), source_image=img_path.name)
        added += 1

    logger.info(f"'{name}': {added} enrolled, {skipped} skipped (no person/face in crop).")
    return added
