"""
/members — enrolled household members.

- GET    /members                 list the roster (name, embedding count, when)
- POST   /members/{name}/photos   upload one enrollment photo (one pose)
- POST   /members/{name}/enroll   build embeddings from the uploaded photos
- DELETE /members/{name}          remove a member (embeddings + photos)

The Flutter app drives in-app enrollment: it captures pose photos on the device
camera, uploads each via /photos, then calls /enroll. Enrollment runs through
the SAME pipeline the recogniser uses (engine/core/enrollment), and reloads the
running pipeline's DB so the new member is recognised without a restart.
"""

from __future__ import annotations

import shutil
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from api.schemas.alert import MemberOut, MemberListOut
from api.services.pipeline import get_pipeline
from engine.core.face_db import FaceDatabase, PROJECT_ROOT

router = APIRouter()

FACES_DIR = PROJECT_ROOT / "data" / "faces"
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


class CaptureOut(BaseModel):
    name: str
    pose: str
    captured: int  # total photos saved for this member so far


class EnrollOut(BaseModel):
    name: str
    status: str               # enrolling | enrolled | failed
    embedding_count: int = 0


class DeleteOut(BaseModel):
    name: str
    removed: int  # embeddings removed


def _safe_name(name: str) -> str:
    """Validate/normalise a member name into a safe folder name."""
    n = name.strip().lower()
    if not n or not all(c.isalnum() or c in {"_", "-"} for c in n):
        raise HTTPException(status_code=400, detail="Name must be letters/digits/_/- only.")
    return n


def _load_db() -> FaceDatabase:
    """Prefer the running pipeline's DB (what recognition matches against);
    fall back to a fresh disk read if the pipeline isn't up."""
    pipeline = get_pipeline()
    if pipeline is not None:
        return pipeline.recognizer.db
    return FaceDatabase()


@router.get("", response_model=MemberListOut, summary="List enrolled members")
async def list_members():
    db = _load_db()
    pipeline = get_pipeline()
    statuses = pipeline.enrollments_snapshot() if pipeline is not None else {}

    members = []
    seen = set()
    for name in db.known_names():
        rows = [m for m in db.metadata if m["name"] == name]
        latest = max((m.get("enrolled_at") for m in rows if m.get("enrolled_at")), default=None)
        st = statuses.get(name, {})
        # A member already in the DB is "enrolled" unless a build is re-running.
        status = st.get("status") if st.get("status") in ("enrolling", "failed") else "enrolled"
        members.append(MemberOut(
            name=name, embedding_count=len(rows), enrolled_at=latest,
            status=status, error=st.get("error"),
        ))
        seen.add(name)

    # Members whose first-ever build is still running (or failed) aren't in the
    # DB yet — surface them so the app can show "enrolling…" / "failed".
    for name, st in statuses.items():
        if name in seen or st.get("status") not in ("enrolling", "failed"):
            continue
        members.append(MemberOut(
            name=name, embedding_count=0, enrolled_at=st.get("enrolled_at"),
            status=st["status"], error=st.get("error"),
        ))

    return MemberListOut(count=len(members), members=members)


@router.post("/{name}/photos", response_model=CaptureOut, summary="Upload one enrollment photo")
async def upload_photo(name: str, file: UploadFile = File(...), pose: str = Query("pose")):
    name = _safe_name(name)
    person_dir = FACES_DIR / name
    person_dir.mkdir(parents=True, exist_ok=True)

    pose_tag = "".join(c for c in pose.lower() if c.isalnum()) or "pose"
    ts = datetime.now().strftime("%H%M%S_%f")[:9]
    (person_dir / f"{name}_{pose_tag}_{ts}.jpg").write_bytes(await file.read())

    captured = sum(1 for f in person_dir.iterdir() if f.suffix.lower() in _IMAGE_EXTS)
    return CaptureOut(name=name, pose=pose_tag, captured=captured)


@router.post("/{name}/enroll", response_model=EnrollOut, summary="Enroll a member from uploaded photos")
async def enroll_member(name: str):
    # Returns immediately: the heavy YOLO/ArcFace build runs on a background
    # worker (live loop paused so it isn't CPU-starved). The app polls /members
    # for the "enrolling" → "enrolled" transition instead of blocking here.
    name = _safe_name(name)
    pipeline = get_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Vision pipeline not available.")

    person_dir = FACES_DIR / name
    photos = [f for f in person_dir.iterdir() if f.suffix.lower() in _IMAGE_EXTS] if person_dir.exists() else []
    if not photos:
        raise HTTPException(status_code=400, detail="No photos uploaded for this member yet.")

    status = pipeline.enroll_async(name, person_dir)
    return EnrollOut(name=name, status=status["status"], embedding_count=status.get("count", 0))


@router.delete("/{name}", response_model=DeleteOut, summary="Remove a member (embeddings + photos)")
def delete_member(name: str):
    name = _safe_name(name)
    db = FaceDatabase()
    removed = db.remove_person(name)
    db.save()

    person_dir = FACES_DIR / name
    if person_dir.exists():
        shutil.rmtree(person_dir, ignore_errors=True)

    pipeline = get_pipeline()
    if pipeline is not None:
        pipeline.forget_enrollment(name)
        pipeline.recognizer.reload()
    return DeleteOut(name=name, removed=removed)
