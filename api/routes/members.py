"""
/members — enrolled household members.

Read-only view of the local face DB: who the system knows and how many
reference embeddings each person has. Useful for the Flutter app to show the
roster and for confirming an enrollment took. Enrollment itself stays a CLI
admin task (scripts/enroll_face.py, capture_enrollment_frames.py).
"""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas.alert import MemberOut, MemberListOut
from api.services.pipeline import get_pipeline
from engine.core.face_db import FaceDatabase

router = APIRouter()


def _load_db() -> FaceDatabase:
    """
    Prefer the running pipeline's DB (what recognition actually matches
    against); fall back to a fresh read of disk if the pipeline isn't up.
    """
    pipeline = get_pipeline()
    if pipeline is not None:
        return pipeline.recognizer.db
    return FaceDatabase()


@router.get("", response_model=MemberListOut, summary="List enrolled members")
async def list_members():
    db = _load_db()
    members = []
    for name in db.known_names():
        rows = [m for m in db.metadata if m["name"] == name]
        latest = max((m.get("enrolled_at") for m in rows if m.get("enrolled_at")), default=None)
        members.append(MemberOut(name=name, embedding_count=len(rows), enrolled_at=latest))
    return MemberListOut(count=len(members), members=members)
