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


class MemberOut(BaseModel):
    """One enrolled household member."""
    name: str
    embedding_count: int
    enrolled_at: str | None = None  # most recent enrollment timestamp
    status: str = "enrolled"        # enrolled | enrolling | failed
    error: str | None = None        # failure detail when status == "failed"


class MemberListOut(BaseModel):
    """Enrolled members response."""
    count: int
    members: list[MemberOut]
