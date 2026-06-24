"""
Phase 2 — Alerter sanity test (no camera, no Firebase).

Fabricates a frame + person bbox and drives AlertService.handle_unknown()
directly to confirm the local path works end-to-end:
    - a snapshot JPEG lands in data/alerts/
    - the stub notifier logs "would send FCM ..."
    - the per-track cooldown suppresses a rapid second alert

Usage:
    python scripts/test_alerter.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from loguru import logger

from engine.core.alerter import build_alert_service


def main():
    # A dummy 720p frame with a bright rectangle standing in for a person.
    frame = np.full((720, 1280, 3), 40, dtype=np.uint8)
    bbox = [500.0, 150.0, 760.0, 680.0]  # x1, y1, x2, y2
    frame[150:680, 500:760] = (120, 180, 220)

    # Short cooldown so we can observe both the alert AND the suppression fast.
    service = build_alert_service()
    service.cooldown_seconds = 2
    logger.info(f"AlertService cooldown set to {service.cooldown_seconds}s for the test.")

    logger.info("First sighting of track #7 (should raise an alert):")
    a1 = service.handle_unknown(track_id=7, frame=frame, bbox=bbox, distance=0.61)
    assert a1 is not None, "First alert should have been raised"
    assert a1.snapshot_path and os.path.exists(a1.snapshot_path), "Snapshot file should exist"
    logger.success(f"Alert raised: {a1.alert_id} (snapshot exists: {os.path.exists(a1.snapshot_path)})")

    logger.info("Immediate second sighting of track #7 (should be suppressed by cooldown):")
    a2 = service.handle_unknown(track_id=7, frame=frame, bbox=bbox, distance=0.61)
    assert a2 is None, "Second alert within cooldown should be suppressed"
    logger.success("Second alert correctly suppressed by cooldown.")

    logger.info("First sighting of a DIFFERENT track #9 (should raise — separate cooldown):")
    a3 = service.handle_unknown(track_id=9, frame=frame, bbox=bbox, distance=0.58)
    assert a3 is not None, "Different track should alert independently"
    logger.success(f"Alert raised for track #9: {a3.alert_id}")

    logger.success("Alerter sanity test PASSED.")


if __name__ == "__main__":
    main()
