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

3. TEMPORAL-CONSISTENCY VOTING (Phase 6) — an identity is never committed from
   a single recognition. Recent results accumulate as votes; a name is only
   committed when it wins a strong majority of the rolling window, and a track
   that never reaches a confident known majority is treated as a stranger.
   This exploits that real members are steady across frames while strangers
   oscillate, removing single-frame false identities. See VOTE_* constants.

This module is deliberately stateless about the recognizer itself —
it only answers "should I recognize this track right now?" and stores
whatever result the caller feeds back in. The actual DeepFace call lives
in recognizer.py (1c-3) and the threading wrapper lives in 1c-5/6.
"""

import time
from collections import Counter, deque
from dataclasses import dataclass, field
from loguru import logger

# How long a track must be continuously visible before recognition fires.
# Prevents wasting a DeepFace call on a person who immediately walks out.
CONFIRM_SECONDS = 1.0

# How often to re-run recognition on an already-identified track.
# Corrects ID swaps from ByteTrack crossing-occlusion within this window.
REVERIFY_SECONDS = 10.0

# ── Temporal-consistency voting (Phase 6 mitigation) ───────────────────────
# A SINGLE recognition frame is unreliable: at consumer-camera quality a
# stranger can momentarily match a known person (measured live: a stranger hit
# distance 0.182 to 'joshua', better than real joshua's own worst frames at
# ~0.35). But a REAL member's identity is steady frame-to-frame while a
# stranger's oscillates. So we never commit an identity from one frame — we keep
# a short rolling window of recent recognition "votes" and only commit
# "recognized as X" when X wins a strong majority. If the window fills without a
# confident known majority, the track is treated as a STRANGER (security-safe
# default: someone we can't consistently recognise is unknown). Costs ~1-2s of
# extra confirmation time; eliminates most single-frame false identities.
VOTE_WINDOW = 5         # number of recent recognition votes considered
VOTE_MIN_AGREE = 4      # one name must win at least this many of the window to commit
_STRANGER = "__stranger__"    # vote token for an "unrecognized" result
_UNCERTAIN = "__uncertain__"  # vote token for an "uncertain" (ambiguous) result


@dataclass
class TrackEntry:
    """State for a single active track_id."""
    track_id: int
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    last_verified: float = 0.0          # 0 = never verified
    name: str | None = None             # None = not yet recognized
    status: str = "pending"             # pending | recognized | unrecognized
    distance: float | None = None       # closest DB distance at last decision (for alert context)
    recognition_in_flight: bool = False # True = a recognition thread is running for this track
    votes: deque = field(default_factory=lambda: deque(maxlen=VOTE_WINDOW))  # recent vote tokens
    confirmed: bool = False             # True once the window has committed a recognized/stranger verdict


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

        status = result.get("status")

        # "no_face" is not a vote — the crop simply had no detectable face this
        # frame. Don't pollute the window; retry promptly.
        if status == "no_face":
            entry.last_verified = 0.0
            return

        # Turn the result into a single vote token and record the distance for
        # alert context.
        if status == "recognized":
            vote = result["name"]
        elif status == "uncertain":
            vote = _UNCERTAIN
        elif status == "unrecognized":
            vote = _STRANGER
        else:
            entry.last_verified = 0.0
            return
        entry.distance = result.get("distance")
        entry.votes.append(vote)

        # Tally the rolling window into a committed verdict.
        decision, name = self._tally(entry.votes)

        if decision == "pending":
            # Not enough agreement yet — keep gathering votes rapidly
            # (last_verified = 0 makes should_recognize() fire again next frame).
            entry.status = "pending"
            entry.confirmed = False
            entry.last_verified = 0.0
            return

        # A verdict is committed; from here re-verify on the slow cadence.
        entry.confirmed = True
        entry.last_verified = time.time()
        if decision == "recognized":
            if entry.name != name or entry.status != "recognized":
                logger.info(
                    f"Track #{track_id} → recognized as '{name}' "
                    f"({entry.votes.count(name)}/{len(entry.votes)} votes agree)."
                )
            entry.name = name
            entry.status = "recognized"
        else:  # "unrecognized"
            if entry.status != "unrecognized":
                logger.info(
                    f"Track #{track_id} → stranger (no name reached {VOTE_MIN_AGREE}/"
                    f"{VOTE_WINDOW} in window {list(entry.votes)})."
                )
            entry.name = None
            entry.status = "unrecognized"

    @staticmethod
    def _tally(votes: "deque") -> tuple[str, str | None]:
        """
        Reduce the recent vote window to a verdict:
            ("recognized", name)   — `name` won >= VOTE_MIN_AGREE of the window
            ("unrecognized", None) — window full, no name reached the majority
            ("pending", None)      — keep gathering votes

        Only real names count toward the majority; _STRANGER / _UNCERTAIN votes
        do not, so a person who can't be consistently recognised as ANY known
        member falls through to "stranger" once the window fills.
        """
        window = list(votes)
        names = Counter(v for v in window if v not in (_STRANGER, _UNCERTAIN))
        if names:
            name, count = names.most_common(1)[0]
            if count >= VOTE_MIN_AGREE:
                return ("recognized", name)
        if len(window) >= VOTE_WINDOW:
            return ("unrecognized", None)
        return ("pending", None)

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

    def status_and_distance(self, track_id: int) -> tuple[str, float | None]:
        """
        Return (status, distance) for a track — the settled recognition state
        the pipeline uses to decide whether to raise an alert. Returns
        ("pending", None) for an unknown/never-seen track_id.
        """
        entry = self._tracks.get(track_id)
        if entry is None:
            return ("pending", None)
        return (entry.status, entry.distance)

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

    def evict_stale(self, active_ids: set[int]) -> list[int]:
        """
        Evict all tracks whose track_id is no longer in the current frame's
        active detections. Call once per frame with the set of track_ids
        returned by detector.track() for that frame — this keeps the state
        dict from accumulating ghost entries indefinitely.

        Returns the list of evicted track_ids so callers (e.g. the pipeline)
        can release any per-track state they hold elsewhere, such as the
        alerter's cooldown bookkeeping.
        """
        stale = [tid for tid in self._tracks if tid not in active_ids]
        for tid in stale:
            self.evict(tid)
        return stale

    @property
    def active_count(self) -> int:
        return len(self._tracks)