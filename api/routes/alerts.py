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
    """Map an internal Alert to the API schema, exposing a fetchable snapshot URL.

    The snapshot locator may be a remote URL (Firebase Storage signed URL) or a
    local file path. For a remote URL the app fetches it directly; for a local
    path we expose the backend's /alerts/<id>/snapshot proxy route.
    """
    snap = alert.snapshot_path
    if snap and snap.startswith(("http://", "https://")):
        snapshot_url = snap
    elif snap:
        snapshot_url = f"/alerts/{alert.alert_id}/snapshot"
    else:
        snapshot_url = None
    return AlertOut(
        alert_id=alert.alert_id,
        track_id=alert.track_id,
        created_at=alert.created_at,
        reason=alert.reason,
        distance=alert.distance,
        snapshot_url=snapshot_url,
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
    match = alerter.get_alert(alert_id)
    if match is None or not match.snapshot_path:
        raise HTTPException(status_code=404, detail="Alert or snapshot not found")
    path = Path(match.snapshot_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file missing")
    return FileResponse(str(path), media_type="image/jpeg")
