"""
API-key authentication — a single shared secret.

Every data route depends on `require_api_key`, which compares the `X-API-Key`
request header against `settings.api_secret_key`. Without it, anyone on the LAN
(or the public ngrok tunnel) could open the camera stream, list/enrol/delete
members, or read alerts. Single-household scope: one shared key, not per-user
accounts (that's a future JWT/identity layer).

`/`, `/health`, `/docs` and `/openapi.json` stay open so liveness checks and the
Swagger UI still work; the Authorize button in /docs accepts the key.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from config.settings import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Depends(_api_key_header)) -> None:
    expected = settings.api_secret_key
    if not expected:
        # No secret configured → auth disabled (dev convenience).
        return
    if key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
