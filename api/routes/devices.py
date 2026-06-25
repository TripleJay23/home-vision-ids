"""
/devices — register FCM device tokens (the push targets).

The Flutter app POSTs its firebase_messaging token here on launch. Tokens are
held in a small file-backed store shared with the notifier (see
engine/core/device_tokens.py).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from engine.core.device_tokens import DeviceTokenStore

router = APIRouter()
_store = DeviceTokenStore()


class TokenIn(BaseModel):
    token: str


class TokenRegisterOut(BaseModel):
    registered: bool      # True if newly added, False if already known
    device_count: int


@router.post("", response_model=TokenRegisterOut, summary="Register an FCM device token")
async def register_device(body: TokenIn):
    added = _store.add(body.token)
    return TokenRegisterOut(registered=added, device_count=len(_store.all()))
