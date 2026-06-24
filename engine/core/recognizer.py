"""
Phase 1c-3 — Face recognizer.

Stateless: given a face/person crop, extracts an embedding via DeepFace and
matches it against the local face_db.py knowledge base using cosine distance.

Does NOT own any per-track timing/state — "when to call this" (the 1-second
deferred-confirmation window, periodic re-verification) is track_state.py's
job (Phase 1c-4), not this module's.
"""

import numpy as np
from deepface import DeepFace
from loguru import logger

from engine.core.face_db import FaceDatabase

EMBEDDING_MODEL = "ArcFace"

# Lighter detector backend than enrollment's "retinaface" — this runs inside
# the live pipeline. Started with "opencv" (fastest, Haar-cascade) but static
# testing showed it producing confidently-wrong matches on real strangers —
# likely weak face alignment feeding noisy embeddings. Tried "mediapipe" next,
# but it hits a currently-unresolved upstream bug (mp.solutions missing on
# recent mediapipe releases, 0.10.31+, multiple open GitHub issues, no fix
# yet). Settled on "yunet" instead: OpenCV's own CNN-based detector — still
# fast, meaningfully better alignment than Haar-cascade "opencv", no broken
# dependency. Threaded recognition (Phase 1c-5/6) means we have CPU headroom
# to spend on accuracy here rather than squeezing every last bit of speed.
LIVE_DETECTOR_BACKEND = "yunet"

# DeepFace's published cosine-distance threshold for ArcFace. Lower distance
# = more similar; below this counts as a match.
MATCH_THRESHOLD = 0.52

# Minimum gap (in cosine distance) required between the best-matching person
# and the closest OTHER enrolled person before we trust the match. A query can
# sit comfortably below MATCH_THRESHOLD yet be almost equidistant between two
# enrolled people — at that point "nearest neighbour wins" is a coin flip and
# the dominant cause of confidently-wrong matches (joshua labelled as noela and
# vice versa). When the margin is this small we return "uncertain" rather than
# committing to a name, and the caller retries on a later frame.
MIN_CONFIDENCE_MARGIN = 0.08


class FaceRecognizer:
    """Matches a face crop against the local known-faces database."""

    def __init__(self):
        self.db = FaceDatabase()
        if self.db.embeddings.size == 0:
            logger.warning("Face DB is empty — recognize() will always return 'unrecognized'.")
        else:
            logger.success(
                f"Face recognizer ready. {len(self.db.metadata)} embeddings, "
                f"{len(self.db.known_names())} known people: {self.db.known_names()}"
            )

    def recognize(self, face_crop: np.ndarray) -> dict:
        """
        Identify a face crop against the known-faces database.

        Returns one of:
            {"status": "no_face",        "name": None, "distance": None}
            {"status": "no_known_faces", "name": None, "distance": None}
            {"status": "recognized",     "name": str,  "distance": float}
            {"status": "uncertain",      "name": str,  "distance": float, "margin": float}
            {"status": "unrecognized",   "name": None, "distance": float}

        "uncertain" means the closest match was below MATCH_THRESHOLD but too
        close to a second enrolled person to trust (margin < MIN_CONFIDENCE_MARGIN).
        Callers should treat it like "no_face" — retry on a later frame, do NOT
        commit the name — rather than as a confirmed identity.
        """
        try:
            results = DeepFace.represent(
                img_path=face_crop,
                model_name=EMBEDDING_MODEL,
                detector_backend=LIVE_DETECTOR_BACKEND,
                enforce_detection=True,
            )
        except ValueError:
            # No face found in this crop (person facing away, occluded, etc.)
            # — distinct from "face found but unknown". Caller should retry,
            # not treat this as a confirmed stranger.
            return {"status": "no_face", "name": None, "distance": None}

        query_embedding = np.asarray(results[0]["embedding"], dtype=np.float32)

        if self.db.embeddings.size == 0:
            return {"status": "no_known_faces", "name": None, "distance": None}

        name, distance, margin = self._best_match(query_embedding)

        if distance >= MATCH_THRESHOLD:
            logger.info(f"Unrecognized face (closest distance: {distance:.3f}, threshold: {MATCH_THRESHOLD})")
            return {"status": "unrecognized", "name": None, "distance": distance}

        # Below threshold, but is the runner-up (a different person) too close?
        if margin < MIN_CONFIDENCE_MARGIN:
            logger.info(
                f"Uncertain match: closest is '{name}' (distance: {distance:.3f}) but margin to next "
                f"person is only {margin:.3f} < {MIN_CONFIDENCE_MARGIN} — not committing."
            )
            return {"status": "uncertain", "name": name, "distance": distance, "margin": margin}

        logger.info(f"Recognized: {name} (distance: {distance:.3f}, margin: {margin:.3f})")
        return {"status": "recognized", "name": name, "distance": distance}

    def _best_match(self, query_embedding: np.ndarray) -> tuple[str, float, float]:
        """
        Find the closest stored embedding by cosine distance.

        Returns (best_name, best_distance, margin) where margin is the gap
        between best_distance and the closest embedding belonging to a
        DIFFERENT person. With only one enrolled person there is no other
        person to confuse them with, so margin is +inf (never uncertain).
        """
        db_embeddings = self.db.embeddings
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        db_norms = db_embeddings / np.linalg.norm(db_embeddings, axis=1, keepdims=True)

        similarities = db_norms @ query_norm  # cosine similarity per row
        distances = 1 - similarities

        best_idx = int(np.argmin(distances))
        best_name = self.db.metadata[best_idx]["name"]
        best_distance = float(distances[best_idx])

        # Closest distance among embeddings NOT belonging to best_name.
        other_distances = [
            float(d) for i, d in enumerate(distances)
            if self.db.metadata[i]["name"] != best_name
        ]
        margin = (min(other_distances) - best_distance) if other_distances else float("inf")

        return best_name, best_distance, margin