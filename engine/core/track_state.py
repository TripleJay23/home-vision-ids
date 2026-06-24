"""
Phase 1c-4 — Per-track state manager.

Owns all per-track_id state: when the track was first seen, what its
recognition status is, and when it was last verified. Enforces two core
design decisions from DESIGN.md:

1. DEFERRED RECOGNITION — DeepFace only runs after a track has been
   continuously visible for CONFIRM_SECONDS (default 1s). Avoids hammering
   the CPU on a detection that immediately walks out of frame.

2. PERIODIC RE-VERIFICATION — even after a track is recognized, DeepFace
   re-runs every REVERIFY_SECONDS (default 10s). This is the mitigation for
   ByteTrack crossing-occlusion ID swaps: if two people's IDs get swapped
   mid-crossing, re-verification catches the mismatch within seconds and
   re-labels the track correctly, rather than leaving a wrong name stuck on
   a person indefinitely.

This module is deliberately stateless about the recognizer itself —
it only answers "should I recognize this track right now?" and stores
whatever result the caller feeds back in. The actual DeepFace call lives
in recognizer.py (1c-3) and the threading wrapper lives in 1c-5/6.
"""

import time
from dataclasses import dataclass, field
from loguru import logger

# How long a track must be continuously visible before recognition fires.
# Prevents wasting a DeepFace call on a person who immediately walks out.
CONFIRM_SECONDS = 1.0

# How often to re-run recognition on an already-identified track.
# Corrects ID swaps from ByteTrack crossing-occlusion within this window.
REVERIFY_SECONDS = 10.0


@dataclass
class TrackEntry:
    """State for a single active track_id."""
    track_id: int
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    last_verified: float = 0.0          # 0 = never verified
    name: str | None = None             # None = not yet recognized
    status: str = "pending"             # pending | recognized | unrecognized
    recognition_in_flight: bool = False # True = a recognition thread is running for this track


class TrackStateManager:
    """
    Manages recognition state for all currently active tracks.

    Typical call pattern per frame (from the pipeline, Phase 1c-5):

        for det in detections:
            track_id = det["track_id"]
            state_manager.update_seen(track_id)

            if state_manager.should_recognize(track_id):
                state_manager.mark_in_flight(track_id)
                # submit recognize(crop) to thread pool
                # on result: state_manager.update_result(track_id, result)

            label = state_manager.get_label(track_id)
            # draw label on frame
    """

    def __init__(self):
        self._tracks: dict[int, TrackEntry] = {}

    # ── Core frame-level calls ────────────────────────────────────────────

    def update_seen(self, track_id: int) -> None:
        """Call once per frame for each active track_id to keep last_seen current."""
        if track_id not in self._tracks:
            self._tracks[track_id] = TrackEntry(track_id=track_id)
            logger.debug(f"Track #{track_id} registered.")
        else:
            self._tracks[track_id].last_seen = time.time()

    def should_recognize(self, track_id: int) -> bool:
        """
        Returns True if this track should trigger a recognition call right now.

        True when ALL of:
        - Track has been visible for >= CONFIRM_SECONDS (deferred window)
        - No recognition is already in flight for this track
        - Either never been recognized yet, OR REVERIFY_SECONDS has elapsed
          since the last verification (periodic re-verification)
        """
        if track_id not in self._tracks:
            return False

        entry = self._tracks[track_id]
        now = time.time()

        # Deferred window: must have been in frame long enough
        if (now - entry.first_seen) < CONFIRM_SECONDS:
            return False

        # Don't stack calls — one in-flight at a time per track
        if entry.recognition_in_flight:
            return False

        # Never verified yet
        if entry.last_verified == 0.0:
            return True

        # Periodic re-verification
        return (now - entry.last_verified) >= REVERIFY_SECONDS

    def mark_in_flight(self, track_id: int) -> None:
        """
        Mark this track as having a recognition call currently running.
        Prevents duplicate calls being submitted for the same track.
        Call this immediately before submitting to the thread pool.
        """
        if track_id in self._tracks:
            self._tracks[track_id].recognition_in_flight = True

    def update_result(self, track_id: int, result: dict) -> None:
        """
        Store the recognition result returned by recognizer.recognize().
        Call this from the thread pool callback when a result arrives.

        result is the dict returned by FaceRecognizer.recognize():
            {"status": "recognized"|"unrecognized"|"no_face"|..., "name": str|None, ...}
        """
        if track_id not in self._tracks:
            # Track may have been evicted while recognition was in flight —
            # silently discard the result rather than re-inserting a ghost entry.
            logger.debug(f"Track #{track_id} result arrived but track already evicted — discarding.")
            return

        entry = self._tracks[track_id]
        entry.recognition_in_flight = False
        entry.last_verified = time.time()

        status = result.get("status")

        if status == "recognized":
            entry.name = result["name"]
            entry.status = "recognized"
            logger.info(f"Track #{track_id} → recognized as '{entry.name}' (distance: {result.get('distance', '?'):.3f})")

        elif status == "unrecognized":
            entry.name = None
            entry.status = "unrecognized"
            logger.info(f"Track #{track_id} → unrecognized stranger (distance: {result.get('distance', '?'):.3f})")

        elif status == "no_face":
            # Face crop didn't yield a detectable face — don't update last_verified
            # so the next should_recognize() call will try again promptly.
            entry.last_verified = 0.0
            logger.debug(f"Track #{track_id} → no face detected in crop, will retry.")

    # ── Label / display ───────────────────────────────────────────────────

    def get_label(self, track_id: int) -> str:
        """
        Returns a display label for this track to overlay on the bounding box.
        """
        if track_id not in self._tracks:
            return "?"

        entry = self._tracks[track_id]

        if entry.status == "pending" or entry.last_verified == 0.0:
            elapsed = time.time() - entry.first_seen
            remaining = max(0.0, CONFIRM_SECONDS - elapsed)
            return f"identifying... ({remaining:.1f}s)" if remaining > 0 else "identifying..."

        if entry.status == "recognized":
            return entry.name

        return "stranger"

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def evict(self, track_id: int) -> None:
        """
        Remove a track that ByteTrack has dropped (person left frame and
        track_buffer expired). Called by the pipeline when a track_id stops
        appearing in detector.track() results.
        """
        if track_id in self._tracks:
            entry = self._tracks.pop(track_id)
            logger.debug(f"Track #{track_id} ({entry.name or 'unidentified'}) evicted.")

    def evict_stale(self, active_ids: set[int]) -> None:
        """
        Evict all tracks whose track_id is no longer in the current frame's
        active detections. Call once per frame with the set of track_ids
        returned by detector.track() for that frame — this keeps the state
        dict from accumulating ghost entries indefinitely.
        """
        stale = [tid for tid in self._tracks if tid not in active_ids]
        for tid in stale:
            self.evict(tid)

    @property
    def active_count(self) -> int:
        return len(self._tracks)