"""
Shared face-crop helper.

Both the live pipeline (runtime) and enrollment must isolate the face region
from a person bounding box the SAME way — identical crops feed identical
embeddings, which is what makes enrolled embeddings and live query embeddings
directly comparable. Keep this the single source of truth for the crop.
"""

from __future__ import annotations

import numpy as np

# Top fraction of a person bounding box (measured from the top) handed to face
# recognition — covers face + neck without the whole body shrinking the face.
FACE_CROP_RATIO = 0.45


def extract_face_crop(
    frame: np.ndarray, bbox: list[float], ratio: float = FACE_CROP_RATIO
) -> np.ndarray:
    """Return the top `ratio` of a person bbox, clamped to the frame bounds."""
    x1, y1, x2, y2 = [int(v) for v in bbox]
    face_h = int((y2 - y1) * ratio)
    x1, y1 = max(0, x1), max(0, y1)
    x2 = min(frame.shape[1], x2)
    y2 = min(frame.shape[0], y1 + face_h)
    return frame[y1:y2, x1:x2].copy()
