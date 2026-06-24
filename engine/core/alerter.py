"""
Phase 2 — Alert pipeline.

When the live pipeline confirms an UNKNOWN person (a tracked person that
recognition has settled on as a stranger), this module turns that event into
an alert: it crops a snapshot, persists it, and dispatches a notification.

DESIGN NOTE — interface-first, Firebase-later
----------------------------------------------
The two cloud-facing concerns are kept behind abstract interfaces so the rest
of the system never imports or knows about Firebase:

    SnapshotStore  — persists the snapshot, returns a locator (path or URL)
    Notifier       — delivers the push notification

Today we run fully locally:
    LocalSnapshotStore  → writes JPEGs to settings.alerts_path (data/alerts/)
    StubNotifier        → logs "would send FCM ..." instead of sending

When Firebase credentials are ready, the swap is a single file change: add a
firebase backend module implementing these same two interfaces (e.g.
FirebaseSnapshotStore + FcmNotifier) and point build_alert_service() at them.
AlertService and every caller stay untouched — no refactor.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

from config.settings import settings


@dataclass
class Alert:
    """A single alert event for one unknown person sighting."""
    alert_id: str
    track_id: int
    created_at: str                      # ISO timestamp
    reason: str = "unknown_person"
    distance: float | None = None        # closest DB distance at decision time, for context
    snapshot_path: str | None = None     # set by the SnapshotStore once persisted


# ── Interfaces (the abstraction seam Firebase slots into) ────────────────────

class SnapshotStore(ABC):
    """Persists an alert snapshot and returns a locator (local path or URL)."""

    @abstractmethod
    def save_crop(self, crop: np.ndarray, alert: Alert) -> str:
        """Persist `crop` for `alert`, return its locator (path/URL)."""
        raise NotImplementedError


class Notifier(ABC):
    """Delivers an alert to the user (push notification, etc.)."""

    @abstractmethod
    def notify(self, alert: Alert) -> None:
        """Dispatch a notification for `alert`."""
        raise NotImplementedError


# ── Local implementations (the only ones wired today) ────────────────────────

class LocalSnapshotStore(SnapshotStore):
    """Writes snapshots to the local filesystem under settings.alerts_path."""

    def __init__(self, alerts_dir: Path | None = None):
        self.alerts_dir = Path(alerts_dir or settings.alerts_path)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

    def save_crop(self, crop: np.ndarray, alert: Alert) -> str:
        path = self.alerts_dir / f"{alert.alert_id}.jpg"
        ok = cv2.imwrite(str(path), crop)
        if not ok:
            # imwrite returns False rather than raising on most failures.
            raise IOError(f"Failed to write alert snapshot to {path}")
        logger.info(f"Alert snapshot saved → {path}")
        return str(path)


class StubNotifier(Notifier):
    """
    Placeholder for the real FCM push. Logs what it *would* send so the full
    alert pipeline is exercised and observable without any Firebase setup.
    """

    def notify(self, alert: Alert) -> None:
        logger.warning(
            f"[STUB] would send FCM push → unknown person (track #{alert.track_id}), "
            f"snapshot={alert.snapshot_path}, distance={alert.distance}"
        )


# ── Orchestrator ─────────────────────────────────────────────────────────────

# Fraction of the person bounding box height, measured from the top, to keep in
# the alert snapshot. Captures head + shoulders — enough for the user to
# recognise the stranger — without the full body dominating the thumbnail.
SNAPSHOT_TOP_RATIO = 0.5


class AlertService:
    """
    Turns 'unknown person confirmed' events into persisted, notified alerts,
    enforcing the per-track cooldown so a single lingering stranger doesn't
    spam notifications.

    Cooldown is keyed on track_id: a stranger has no stable identity to dedupe
    on, but keeps one track_id while continuously visible, so this caps alerts
    at one per CONTINUOUS sighting per cooldown window — matching the
    "1 alert per unknown person per 60s" constraint in AGENTS.md.
    """

    def __init__(
        self,
        store: SnapshotStore,
        notifier: Notifier,
        cooldown_seconds: int | None = None,
    ):
        self.store = store
        self.notifier = notifier
        self.cooldown_seconds = (
            cooldown_seconds if cooldown_seconds is not None
            else settings.alert_cooldown_seconds
        )
        self._last_alert_at: dict[int, float] = {}  # track_id -> monotonic time

    def should_alert(self, track_id: int) -> bool:
        """True if this track hasn't alerted within the cooldown window."""
        last = self._last_alert_at.get(track_id)
        return last is None or (time.monotonic() - last) >= self.cooldown_seconds

    def handle_unknown(
        self,
        track_id: int,
        frame: np.ndarray,
        bbox: list[float],
        distance: float | None = None,
    ) -> Alert | None:
        """
        Process a confirmed-unknown person. Returns the Alert that was raised,
        or None if suppressed by the cooldown.
        """
        if not self.should_alert(track_id):
            return None

        crop = self._crop_snapshot(frame, bbox)
        if crop.size == 0:
            logger.warning(f"Track #{track_id}: empty snapshot crop, skipping alert.")
            return None

        now = datetime.now()
        alert = Alert(
            alert_id=f"{now.strftime('%Y%m%d_%H%M%S')}_track{track_id}",
            track_id=track_id,
            created_at=now.isoformat(timespec="seconds"),
            distance=distance,
        )

        try:
            alert.snapshot_path = self.store.save_crop(crop, alert)
            self.notifier.notify(alert)
        except Exception as e:
            # An alert failing to persist/notify must not crash the vision loop.
            logger.error(f"Alert dispatch failed for track #{track_id}: {e}")
            return None

        self._last_alert_at[track_id] = time.monotonic()
        logger.warning(f"ALERT raised: unknown person (track #{track_id}) → {alert.alert_id}")
        return alert

    def forget(self, track_id: int) -> None:
        """Drop cooldown state for an evicted track to avoid unbounded growth."""
        self._last_alert_at.pop(track_id, None)

    @staticmethod
    def _crop_snapshot(frame: np.ndarray, bbox: list[float]) -> np.ndarray:
        """Crop the head/shoulders region of a person bbox for the snapshot."""
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y1 + int((y2 - y1) * SNAPSHOT_TOP_RATIO))
        return frame[y1:y2, x1:x2].copy()


# ── Factory — the single swap point for Firebase ─────────────────────────────

def build_alert_service() -> AlertService:
    """
    Construct the AlertService with the active backends.

    TODAY: local snapshot store + stubbed FCM notifier (no Firebase needed).
    LATER: when settings carry valid Firebase credentials, branch here to
    return AlertService(FirebaseSnapshotStore(), FcmNotifier()). That is the
    ONLY place that needs to change — see module docstring.
    """
    return AlertService(store=LocalSnapshotStore(), notifier=StubNotifier())
