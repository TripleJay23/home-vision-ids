"""
/alerts — recent unknown-person alerts and their snapshots.

Reads from the running pipeline's AlertService (in-memory ring buffer for now;
this is where a persistent store / Firebase query slots in later).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.schemas.alert import AlertOut, AlertListOut
from api.services.pipeline import get_pipeline

router = APIRouter()


def _to_out(alert) -> AlertOut:
    """Map an internal Alert to the API schema, exposing a fetchable snapshot URL."""
    return AlertOut(
        alert_id=alert.alert_id,
        track_id=alert.track_id,
        created_at=alert.created_at,
        reason=alert.reason,
        distance=alert.distance,
        snapshot_url=f"/alerts/{alert.alert_id}/snapshot" if alert.snapshot_path else None,
    )


def _require_alerter():
    pipeline = get_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Vision pipeline is not running")
    return pipeline.alerter


@router.get("", response_model=AlertListOut, summary="List recent alerts")
async def list_alerts(limit: int = Query(20, ge=1, le=100)):
    alerter = _require_alerter()
    alerts = [_to_out(a) for a in alerter.recent_alerts(limit=limit)]
    return AlertListOut(count=len(alerts), alerts=alerts)


@router.get("/{alert_id}/snapshot", summary="Fetch an alert's snapshot image")
async def alert_snapshot(alert_id: str):
    alerter = _require_alerter()
    match = next((a for a in alerter.recent_alerts(limit=100) if a.alert_id == alert_id), None)
    if match is None or not match.snapshot_path:
        raise HTTPException(status_code=404, detail="Alert or snapshot not found")
    path = Path(match.snapshot_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file missing")
    return FileResponse(str(path), media_type="image/jpeg")
