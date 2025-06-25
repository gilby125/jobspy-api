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
    # Fix Celery 6.0+ deprecation warnings
    broker_connection_retry_on_startup=getattr(settings, 'CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP', True),
    broker_connection_retry=getattr(settings, 'CELERY_BROKER_CONNECTION_RETRY', True),
    # Fix connection loss issues
    worker_cancel_long_running_tasks_on_connection_loss=getattr(settings, 'CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS', True),
    broker_connection_retry_delay=getattr(settings, 'CELERY_BROKER_CONNECTION_RETRY_DELAY', 2.0),
    broker_connection_max_retries=getattr(settings, 'CELERY_BROKER_CONNECTION_MAX_RETRIES', 10),
    broker_heartbeat=getattr(settings, 'CELERY_BROKER_HEARTBEAT', 30),
    broker_pool_limit=10,
    worker_send_task_events=True,
    task_send_sent_event=True,
    beat_schedule={
        'check-pending-searches': {
            'task': 'app.tasks.check_pending_recurring_searches',
            'schedule': 60.0,  # Check every minute
        },
    },
)

# Configure task routing - use default celery queue for simplicity
celery_app.conf.task_routes = {}