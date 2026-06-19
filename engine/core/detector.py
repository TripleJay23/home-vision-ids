from ultralytics import YOLO
from loguru import logger
import numpy as np

from config.settings import settings

# Classes we care about (COCO dataset indices)
TARGET_CLASSES = {
    0: "person",
    15: "cat",
    16: "dog",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
}


class ObjectDetector:
    """
    Wraps YOLOv8n for real-time object detection.
    Only processes classes defined in TARGET_CLASSES.
    """

    def __init__(self):
        model_path = settings.models_path / settings.yolo_model
        logger.info(f"Loading YOLO model from: {model_path}")
        self.model = YOLO(str(model_path) if model_path.exists() else settings.yolo_model)
        self.confidence = settings.confidence_threshold
        logger.success("YOLO model loaded.")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run detection on a single frame.
        Returns list of detections: [{class, label, confidence, bbox}]
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
                    "bbox": box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                })

        return detections