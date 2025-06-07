"""
Celery application for job orchestration.
Manages scraping tasks, scheduling, and coordination with Go workers.
"""
import os
import logging
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'jobspy_orchestrator',
    broker=settings.CELERY_BROKER_URL or 'redis://localhost:6379/1',
    backend=settings.CELERY_RESULT_BACKEND or 'redis://localhost:6379/2',
    include=[
        'app.workers.orchestrator',
        'app.workers.data_processor',
        'app.workers.scheduler'
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        'app.workers.orchestrator.*': {'queue': 'orchestrator'},
        'app.workers.data_processor.*': {'queue': 'data_processor'},
        'app.workers.scheduler.*': {'queue': 'scheduler'},
    },
    
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        'visibility_timeout': 3600,
        'retry_policy': {
            'timeout': 5.0
        }
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Broker settings
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Daily scraping jobs
        'daily_indeed_scraping': {
            'task': 'app.workers.scheduler.schedule_daily_scraping',
            'schedule': crontab(hour=6, minute=0),  # 6 AM daily
            'args': ('indeed',),
            'options': {'queue': 'scheduler'}
        },
        'daily_linkedin_scraping': {
            'task': 'app.workers.scheduler.schedule_daily_scraping',
            'schedule': crontab(hour=7, minute=0),  # 7 AM daily
            'args': ('linkedin',),
            'options': {'queue': 'scheduler'}
        },
        
        # Health monitoring
        'monitor_scraper_health': {
            'task': 'app.workers.orchestrator.monitor_scraper_health',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'orchestrator'}
        },
        
        # Data cleanup
        'cleanup_old_data': {
            'task': 'app.workers.data_processor.cleanup_old_data',
            'schedule': crontab(hour=2, minute=0),  # 2 AM daily
            'options': {'queue': 'data_processor'}
        },
        
        # Analytics updates
        'update_company_trends': {
            'task': 'app.workers.data_processor.update_company_trends',
            'schedule': crontab(hour=1, minute=0),  # 1 AM daily
            'options': {'queue': 'data_processor'}
        },
        
        # Queue monitoring
        'monitor_queue_health': {
            'task': 'app.workers.orchestrator.monitor_queue_health',
            'schedule': 60.0,  # Every minute
            'options': {'queue': 'orchestrator'}
        }
    },
)

# Optional: Add custom error handler
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery functionality."""
    logger.info(f'Request: {self.request!r}')
    return 'Debug task completed'

if __name__ == '__main__':
    celery_app.start()