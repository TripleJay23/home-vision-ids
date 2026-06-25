"""
Firebase implementations of the alerter's SnapshotStore + Notifier interfaces.

This is the ONLY module that imports firebase_admin. alerter.build_alert_service()
switches to these when valid credentials are present; otherwise the local/stub
backends run. Nothing else in the system imports or knows about Firebase — see
the design note in alerter.py.
"""

from __future__ import annotations

from datetime import timedelta

import cv2
import numpy as np
import firebase_admin
from firebase_admin import credentials, messaging, storage
from loguru import logger

from config.settings import settings
from engine.core.alerter import Alert, Notifier, SnapshotStore
from engine.core.device_tokens import DeviceTokenStore


def init_firebase() -> None:
    """Initialise the firebase_admin default app once (idempotent).

    The Storage bucket is attached only when one is actually configured — FCM
    works without it, so a Storage-less project still gets push notifications.
    """
    if firebase_admin._apps:  # already initialised
        return
    cred = credentials.Certificate(str(settings.firebase_credentials_path))
    bucket = settings.firebase_storage_bucket or ""
    options = {"storageBucket": bucket} if bucket and "your-app" not in bucket else None
    firebase_admin.initialize_app(cred, options)
    logger.success(
        f"Firebase initialised ({'bucket: ' + bucket if options else 'FCM only, no Storage bucket'})."
    )


class FirebaseSnapshotStore(SnapshotStore):
    """Uploads the snapshot to Firebase Storage and returns a signed URL.

    A signed URL (rather than a public object) means the phone can load the
    image from anywhere without auth, and access expires on its own.
    """

    SIGNED_URL_DAYS = 7

    def save_crop(self, crop: np.ndarray, alert: Alert) -> str:
        ok, buf = cv2.imencode(".jpg", crop)
        if not ok:
            raise IOError("Failed to JPEG-encode alert snapshot")
        bucket = storage.bucket()
        blob = bucket.blob(f"alerts/{alert.alert_id}.jpg")
        blob.upload_from_string(buf.tobytes(), content_type="image/jpeg")
        url = blob.generate_signed_url(
            expiration=timedelta(days=self.SIGNED_URL_DAYS), version="v4"
        )
        logger.info(f"Alert snapshot uploaded → gs://{bucket.name}/{blob.name}")
        return url


class FcmNotifier(Notifier):
    """Sends an FCM push to every registered device token."""

    def __init__(self, tokens: DeviceTokenStore | None = None):
        self.tokens = tokens or DeviceTokenStore()

    def notify(self, alert: Alert) -> None:
        tokens = self.tokens.all()
        if not tokens:
            logger.warning(f"Alert {alert.alert_id}: no registered devices to notify.")
            return

        # Only forward a snapshot URL the phone can actually load (a remote
        # Storage URL). For a local snapshot we send an empty string and the app
        # rebuilds the URL from its configured backend base URL + alert_id
        # (-> /alerts/<id>/snapshot), exactly like the /alerts REST response.
        snap = alert.snapshot_path or ""
        remote_url = snap if snap.startswith(("http://", "https://")) else ""
        data = {
            "alert_id": alert.alert_id,
            "track_id": str(alert.track_id),
            "reason": alert.reason,
            "snapshot_url": remote_url,
            "created_at": alert.created_at,
        }
        messages = [
            messaging.Message(
                notification=messaging.Notification(
                    title="Unknown person detected",
                    body="Home Vision IDS spotted someone it doesn't recognise.",
                ),
                data=data,
                token=t,
            )
            for t in tokens
        ]
        resp = messaging.send_each(messages)
        logger.info(
            f"FCM push for {alert.alert_id}: {resp.success_count} sent, {resp.failure_count} failed."
        )
        # Prune tokens FCM reports as no longer registered (app uninstalled, etc.).
        for token, result in zip(tokens, resp.responses):
            if not result.success and isinstance(result.exception, messaging.UnregisteredError):
                self.tokens.remove(token)
                logger.info("Removed a stale (unregistered) FCM token.")
