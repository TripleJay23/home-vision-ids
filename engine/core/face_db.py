"""
Local face embeddings database.

Stores known-face embeddings as a NumPy array (data/embeddings/known_embeddings.npy)
with parallel JSON metadata (data/embeddings/known_embeddings.json) mapping each
row to a person's name and enrollment details.

Local-only by design — no cloud sync, no external service. See DESIGN.md.

Design note: each enrolled image is stored as its OWN embedding row, not
averaged into a single per-person vector. This gives the recognizer (1c-3)
multiple reference points per person to match against — covering different
angles/lighting — rather than collapsing that variation into one centroid
that might not represent any single real pose well.
"""

import json
from pathlib import Path
from datetime import datetime
import numpy as np
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EMBEDDINGS_DIR = PROJECT_ROOT / "data" / "embeddings"
EMBEDDINGS_NPY = EMBEDDINGS_DIR / "known_embeddings.npy"
EMBEDDINGS_JSON = EMBEDDINGS_DIR / "known_embeddings.json"


class FaceDatabase:
    """
    Manages the local knowledge base of known-face embeddings.

    Each row in the .npy array corresponds 1:1 with an entry in the .json
    metadata list (same index = same person/image).
    """

    def __init__(self):
        self.embeddings: np.ndarray = np.empty((0, 0))  # (N, dim)
        self.metadata: list[dict] = []  # [{name, source_image, enrolled_at}, ...]
        self._load()

    def _load(self) -> None:
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

        if EMBEDDINGS_NPY.exists() and EMBEDDINGS_JSON.exists():
            self.embeddings = np.load(EMBEDDINGS_NPY)
            with open(EMBEDDINGS_JSON, "r") as f:
                self.metadata = json.load(f)
            logger.info(
                f"Loaded face DB: {len(self.metadata)} embeddings, "
                f"{len(self.known_names())} known people."
            )
        else:
            logger.info("No existing face DB found — starting empty.")

    def add_embedding(self, name: str, embedding: list[float], source_image: str) -> None:
        """Append a new embedding for `name` to the database (in-memory only — call save())."""
        embedding = np.asarray(embedding, dtype=np.float32).reshape(1, -1)

        if self.embeddings.size == 0:
            self.embeddings = embedding
        else:
            if embedding.shape[1] != self.embeddings.shape[1]:
                raise ValueError(
                    f"Embedding dim mismatch: DB has {self.embeddings.shape[1]}, "
                    f"got {embedding.shape[1]}. Mixing embedding models?"
                )
            self.embeddings = np.vstack([self.embeddings, embedding])

        self.metadata.append({
            "name": name,
            "source_image": source_image,
            "enrolled_at": datetime.now().isoformat(timespec="seconds"),
        })

    def save(self) -> None:
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        np.save(EMBEDDINGS_NPY, self.embeddings)
        with open(EMBEDDINGS_JSON, "w") as f:
            json.dump(self.metadata, f, indent=2)
        logger.success(
            f"Saved face DB: {len(self.metadata)} embeddings, "
            f"{len(self.known_names())} known people."
        )

    def remove_person(self, name: str) -> int:
        """
        Remove all existing embeddings for `name` (in-memory only — call
        save() after). Used by enroll_face.py so re-running enrollment for
        someone replaces their old data rather than silently duplicating
        entries or accumulating stale rows from photos later removed from
        their folder.
        """
        keep = [i for i, m in enumerate(self.metadata) if m["name"] != name]
        removed = len(self.metadata) - len(keep)
        if removed:
            self.embeddings = self.embeddings[keep] if self.embeddings.size > 0 else self.embeddings
            self.metadata = [self.metadata[i] for i in keep]
        return removed

    def known_names(self) -> list[str]:
        return sorted(set(m["name"] for m in self.metadata))

    def count_for(self, name: str) -> int:
        return sum(1 for m in self.metadata if m["name"] == name)