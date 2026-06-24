"""
/stream — live annotated MJPEG feed.

Serves the pipeline's latest annotated frame as multipart/x-mixed-replace, the
simplest stream Flutter's Image.network() can consume (see DESIGN.md #7).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config.settings import settings
from api.services.pipeline import get_pipeline

router = APIRouter()

_BOUNDARY = "frame"


async def _mjpeg_generator():
    """Yield the latest JPEG frame repeatedly as an MJPEG multipart stream."""
    pipeline = get_pipeline()
    # Pace the stream to the configured FPS rather than busy-looping.
    frame_interval = 1.0 / max(1, settings.stream_fps)

    while True:
        jpeg = pipeline.get_jpeg() if pipeline else None
        if jpeg is not None:
            yield (
                b"--" + _BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                + jpeg + b"\r\n"
            )
        await asyncio.sleep(frame_interval)


@router.get("", summary="Live annotated MJPEG stream")
async def stream():
    pipeline = get_pipeline()
    if pipeline is None or not pipeline._running:
        raise HTTPException(status_code=503, detail="Vision pipeline is not running (camera unavailable?)")
    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )
