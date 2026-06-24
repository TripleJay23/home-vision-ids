"""Pydantic response schemas for the alerts API."""

from __future__ import annotations

from pydantic import BaseModel


class AlertOut(BaseModel):
    """One alert as returned by the API."""
    alert_id: str
    track_id: int
    created_at: str
    reason: str
    distance: float | None = None
    snapshot_url: str | None = None  # API path to fetch the snapshot image


class AlertListOut(BaseModel):
    """Recent alerts response."""
    count: int
    alerts: list[AlertOut]
