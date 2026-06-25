"""
Local registry of FCM device tokens — the push targets.

Backed by a small JSON file so registrations survive restarts. The Flutter app
POSTs its token to /devices on launch; FcmNotifier reads them at send time.
The file is the source of truth, re-read on each operation, so the API request
thread and the pipeline's notifier thread stay consistent without shared state.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from loguru import logger

from config.settings import settings


class DeviceTokenStore:
    """Thread-safe, file-backed set of FCM device tokens."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.fcm_tokens_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def all(self) -> list[str]:
        with self._lock:
            return self._load()

    def add(self, token: str) -> bool:
        """Register a token. Returns True if newly added, False if already known."""
        token = token.strip()
        if not token:
            return False
        with self._lock:
            tokens = self._load()
            if token in tokens:
                return False
            tokens.append(token)
            self._save(tokens)
            logger.info(f"Registered FCM device token (now {len(tokens)} device(s)).")
            return True

    def remove(self, token: str) -> None:
        with self._lock:
            tokens = self._load()
            if token in tokens:
                tokens.remove(token)
                self._save(tokens)

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Could not read FCM token store at {self.path}; treating as empty.")
            return []

    def _save(self, tokens: list[str]) -> None:
        self.path.write_text(json.dumps(tokens, indent=2))
