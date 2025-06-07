"""
Celery application for job scheduling and background tasks.
"""
from celery import Celery
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "jobspy",
    broker=getattr(settings, 'CELERY_BROKER_URL', None) or settings.REDIS_URL or "redis://localhost:6379/1",
    backend=getattr(settings, 'CELERY_RESULT_BACKEND', None) or settings.REDIS_URL or "redis://localhost:6379/2",
    include=["app.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
    result_expires=3600,  # 1 hour
    beat_schedule={
        # Add any periodic tasks here
    },
)

# Configure task routing - use default celery queue for simplicity
celery_app.conf.task_routes = {}