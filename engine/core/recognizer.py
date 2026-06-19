from deepface import DeepFace
from loguru import logger
import numpy as np
import time

from config.settings import settings


class FaceRecognizer:
    """
    Wraps DeepFace for face recognition against the local knowledge base.
    Only runs recognition when a person has been in frame long enough
    (controlled by PERSON_CONFIRM_SECONDS) to avoid hammering the CPU.
    """

    def __init__(self):
        self.db_path = str(settings.faces_db_path)
        self.model_name = settings.face_model
        self.confirm_seconds = settings.person_confirm_seconds
        self._seen_tracker: dict[str, float] = {}  # track_id -> first_seen_timestamp
        logger.info(f"Face recognizer ready. DB: {self.db_path} | Model: {self.model_name}")

    def should_recognize(self, track_id: str) -> bool:
        """
        Returns True only if this person has been tracked for long enough.
        Prevents running DeepFace on every single frame.
        """
        now = time.time()
        if track_id not in self._seen_tracker:
            self._seen_tracker[track_id] = now
            return False
        return (now - self._seen_tracker[track_id]) >= self.confirm_seconds

    def recognize(self, face_crop: np.ndarray) -> dict:
        """
        Identify a face crop against the knowledge base.
        Returns {"known": bool, "name": str | None, "distance": float}
        """
        try:
            results = DeepFace.find(
                img_path=face_crop,
                db_path=self.db_path,
                model_name=self.model_name,
                enforce_detection=False,
                silent=True,
            )

            if results and len(results[0]) > 0:
                top = results[0].iloc[0]
                name = top["identity"].split("/")[-2]  # folder name = person name
                distance = float(top["distance"])
                logger.info(f"Recognized: {name} (distance: {distance:.3f})")
                return {"known": True, "name": name, "distance": distance}

        except Exception as e:
            logger.warning(f"Recognition failed: {e}")

        return {"known": False, "name": None, "distance": 1.0}

    def clear_tracker(self, track_id: str):
        """Call when a person leaves the frame."""
        self._seen_tracker.pop(track_id, None)