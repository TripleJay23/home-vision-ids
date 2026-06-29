"""
SQLite-backed persistent store for alert records.

Phase 2 kept recent alerts in an in-memory ring buffer, so they vanished on
every backend restart. This repository persists the alert *records* (the
snapshot JPEGs already live on disk) to a small SQLite database, so the alert
history — and the ability to serve a snapshot by id — survives restarts. It is
the natural migration point to Postgres later (same method surface).

Thread-safety: the pipeline thread writes (`add`) while the API threadpool reads
(`recent`/`get`). One shared connection with `check_same_thread=False` guarded by
a lock keeps those concurrent calls safe.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from loguru import logger


class AlertStore:
    """Persistent alert-record store (SQLite)."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info(f"Alert store ready ({self.count()} alerts persisted) → {self.db_path}")

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id      TEXT PRIMARY KEY,
                    track_id      INTEGER NOT NULL,
                    created_at    TEXT NOT NULL,
                    reason        TEXT NOT NULL,
                    distance      REAL,
                    snapshot_path TEXT
                )
                """
            )
            self._conn.commit()

    def add(self, alert) -> None:
        """Persist one alert (idempotent on alert_id)."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO alerts "
                "(alert_id, track_id, created_at, reason, distance, snapshot_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (alert.alert_id, alert.track_id, alert.created_at,
                 alert.reason, alert.distance, alert.snapshot_path),
            )
            self._conn.commit()

    def recent(self, limit: int = 20):
        """Most recent alerts, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._to_alert(r) for r in rows]

    def get(self, alert_id: str):
        """One alert by id, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)
            ).fetchone()
        return self._to_alert(row) if row is not None else None

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

    @staticmethod
    def _to_alert(row: sqlite3.Row):
        # Imported lazily to avoid a circular import (alerter imports this module).
        from engine.core.alerter import Alert
        return Alert(
            alert_id=row["alert_id"],
            track_id=row["track_id"],
            created_at=row["created_at"],
            reason=row["reason"],
            distance=row["distance"],
            snapshot_path=row["snapshot_path"],
        )
