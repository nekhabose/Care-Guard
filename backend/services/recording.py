"""
RecordingStore — copy Twilio call recordings into KMS-encrypted S3 (HIPAA §164.312).

Call recordings are PHI. Twilio retains the master copy on its BAA-covered
platform; we pull completed recordings into our own bucket encrypted with a
customer-managed KMS key (SSE-KMS), tagged for the lifecycle/retention policy in
``tasks.retention``. The transport is abstracted so dev can use a no-op store.
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RecordingStore(ABC):
    @abstractmethod
    async def store_recording(self, session_id: uuid.UUID, recording_url: str) -> str | None:
        """Persist a recording and return its storage key (or None if skipped)."""
        ...

    @abstractmethod
    async def delete_recording(self, s3_key: str) -> None:
        """Delete a stored recording (right to erasure / retention sweep)."""
        ...


class NoOpRecordingStore(RecordingStore):
    """Used in dev/tests and whenever recording capture is disabled."""

    async def store_recording(self, session_id: uuid.UUID, recording_url: str) -> str | None:
        logger.info("Recording capture disabled session_id=%s", session_id)
        return None

    async def delete_recording(self, s3_key: str) -> None:
        logger.info("Recording delete is a no-op key=%s", s3_key)


class S3RecordingStore(RecordingStore):
    """Downloads from Twilio (authenticated) and uploads to KMS-encrypted S3."""

    def __init__(self) -> None:
        import boto3  # lazy — AWS SDK not needed when recordings are off

        self._s3 = boto3.client("s3", region_name=settings.aws_region)
        self._bucket = settings.recordings_s3_bucket
        self._kms_key_id = settings.kms_key_id

    async def store_recording(self, session_id: uuid.UUID, recording_url: str) -> str | None:
        # Twilio recording media needs HTTP basic auth with the account creds.
        media_url = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"
        async with httpx.AsyncClient(timeout=60) as http:
            resp = await http.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            resp.raise_for_status()
            audio = resp.content

        key = f"recordings/{session_id}.mp3"
        import asyncio

        # boto3 is sync — offload so we don't block the event loop.
        await asyncio.to_thread(
            self._s3.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=audio,
            ContentType="audio/mpeg",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self._kms_key_id,
            # Tag drives the S3 lifecycle expiry / retention sweep.
            Tagging="data_class=phi&retention=recording",
        )
        logger.info("Recording stored session_id=%s key=%s", session_id, key)
        return key

    async def delete_recording(self, s3_key: str) -> None:
        import asyncio

        await asyncio.to_thread(self._s3.delete_object, Bucket=self._bucket, Key=s3_key)
        logger.info("Recording deleted key=%s", s3_key)


def get_recording_store() -> RecordingStore:
    """Build the recording store. Falls back to no-op when disabled/misconfigured."""
    if not settings.recordings_enabled:
        return NoOpRecordingStore()
    try:
        return S3RecordingStore()
    except Exception:
        logger.exception("S3RecordingStore init failed; recordings will not be captured")
        return NoOpRecordingStore()
