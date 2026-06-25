from celery import Celery
from config import get_settings

settings = get_settings()

celery_app = Celery(
    "careguard",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks.outreach", "tasks.retention"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Persist return values so callers can fetch them via AsyncResult(task_id).
    task_track_started=True,
    task_ignore_result=False,
    result_extended=True,
    result_expires=86400,  # keep results for 24h
)

# Retention sweep (HIPAA data-lifecycle): purge recordings past their window.
celery_app.conf.beat_schedule = {
    "purge-expired-recordings": {
        "task": "tasks.retention.purge_expired_recordings",
        "schedule": 86400.0,  # daily
    },
}
