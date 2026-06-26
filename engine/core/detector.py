from pathlib import Path
from ultralytics import YOLO
from loguru import logger
import numpy as np

from config.settings import settings

TARGET_CLASSES = {
    0: "person",
    15: "cat",
    16: "dog",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
}

# Custom ByteTrack config — tuned track_buffer for re-entry stability.
# See config/tracker/bytetrack_custom.yaml for reasoning.
TRACKER_CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "tracker" / "bytetrack_custom.yaml"
logger.info(f"Tracker config path: {TRACKER_CONFIG} | exists: {TRACKER_CONFIG.exists()}")

class ObjectDetector:
    def __init__(self):
        model_path = settings.models_path / settings.yolo_model
        logger.info(f"Loading YOLO model from: {model_path}")
        self.model = YOLO(str(model_path) if model_path.exists() else settings.yolo_model)
        self.confidence = settings.confidence_threshold
        logger.success("YOLO model loaded.")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run detection only (no tracking) on a single frame. Used by enrollment,
        which processes independent still images and only needs person boxes —
        not stable track IDs. Mirrors track() minus the ByteTrack association.
        """
        results = self.model(
            frame,
            conf=self.confidence,
            classes=list(TARGET_CLASSES.keys()),
            verbose=False,
        )

        detections = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                detections.append({
                    "class_id": class_id,
                    "label": TARGET_CLASSES.get(class_id, "unknown"),
                    "confidence": float(box.conf[0]),
                    "bbox": box.xyxy[0].tolist(),
                })
        return detections

    def track(self, frame: np.ndarray) -> list[dict]:
        """
        Run detection + ByteTrack tracking on a single frame, using the
        tuned tracker config (extended track_buffer).
        """
        results = self.model.track(
            frame,
            conf=self.confidence,
            classes=list(TARGET_CLASSES.keys()),
            persist=True,
            tracker=str(TRACKER_CONFIG),
            verbose=False,
        )

        detections = []
        for result in results:
            has_ids = result.boxes.id is not None
            for i, box in enumerate(result.boxes):
                class_id = int(box.cls[0])
                track_id = int(result.boxes.id[i]) if has_ids else None
                detections.append({
                    "class_id": class_id,
                    "label": TARGET_CLASSES.get(class_id, "unknown"),
                    "confidence": float(box.conf[0]),
                    "bbox": box.xyxy[0].tolist(),
                    "track_id": track_id,
                })

        return detections