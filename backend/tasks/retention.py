"""
Data-retention tasks (HIPAA — minimum necessary & disposal).

Call recordings are PHI and must not be kept indefinitely. This sweep deletes
S3 recording objects older than ``RECORDING_RETENTION_DAYS`` and clears the
pointer on the session. Belt-and-suspenders alongside the S3 lifecycle rule
configured by ``ensure_recording_lifecycle``.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config import get_settings
from database import AsyncSessionLocal
from models.db import OutreachSession

from .celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def ensure_recording_lifecycle() -> None:
    """Idempotently install an S3 lifecycle rule expiring recordings.

    Run once at deploy time. Defence in depth: even if the purge task never
    runs, S3 itself expires the objects.
    """
    if not (settings.recordings_enabled and settings.recordings_s3_bucket):
        return
    import boto3

    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.put_bucket_lifecycle_configuration(
        Bucket=settings.recordings_s3_bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "expire-call-recordings",
                    "Filter": {"Prefix": "recordings/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": settings.recording_retention_days},
                }
            ]
        },
    )
    logger.info(
        "Installed S3 recording lifecycle bucket=%s days=%s",
        settings.recordings_s3_bucket, settings.recording_retention_days,
    )


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def purge_expired_recordings(self) -> dict:
    """Delete recordings older than the retention window. Returns a summary."""
    try:
        return asyncio.run(_purge())
    except Exception as exc:
        logger.exception("purge_expired_recordings failed")
        raise self.retry(exc=exc)


async def _purge() -> dict:
    if not settings.recordings_enabled:
        return {"purged": 0, "skipped": "recordings_disabled"}

    import boto3

    s3 = boto3.client("s3", region_name=settings.aws_region)
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.recording_retention_days)

    purged = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OutreachSession).where(
                OutreachSession.recording_s3_key.is_not(None),
                OutreachSession.created_at < cutoff,
            )
        )
        sessions = list(result.scalars().all())
        for session in sessions:
            key = session.recording_s3_key
            try:
                await asyncio.to_thread(
                    s3.delete_object, Bucket=settings.recordings_s3_bucket, Key=key
                )
            except Exception:
                logger.exception("Failed to delete recording session_id=%s", session.id)
                continue
            session.recording_s3_key = None
            purged += 1
        await db.commit()

    logger.info("purge_expired_recordings done purged=%s", purged)
    return {"purged": purged}


__all__ = ["ensure_recording_lifecycle", "purge_expired_recordings"]
