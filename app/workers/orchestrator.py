"""
Python Celery orchestrator for managing Go scraper workers.
Handles task distribution, monitoring, and result processing.
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from celery import Task
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.workers.message_protocol import (
    MessageProtocol, ScrapingTask, ScrapingTaskParams, ScraperType, 
    TaskStatus, HealthStatus
)
from app.db.database import SessionLocal
from app.models.tracking_models import ScrapingRun, Company, JobPosting
from app.config import settings

logger = logging.getLogger(__name__)


class ScrapingOrchestrator:
    """Orchestrates scraping tasks and manages Go workers."""
    
    def __init__(self):
        self.message_protocol = MessageProtocol()
        self.logger = logging.getLogger(f"{__name__}.ScrapingOrchestrator")
    
    def create_scraping_task(self, scraper_type: ScraperType, 
                           search_params: Dict) -> ScrapingTask:
        """
        Create a new scraping task.
        
        Args:
            scraper_type: Type of scraper to use
            search_params: Search parameters
            
        Returns:
            ScrapingTask instance
        """
        params = ScrapingTaskParams(
            search_term=search_params.get('search_term', ''),
            location=search_params.get('location', ''),
            results_wanted=search_params.get('results_wanted', 50),
            job_type=search_params.get('job_type'),
            experience_level=search_params.get('experience_level'),
            is_remote=search_params.get('is_remote'),
            salary_min=search_params.get('salary_min'),
            salary_max=search_params.get('salary_max'),
            proxy=search_params.get('proxy'),
            user_agent=search_params.get('user_agent'),
            delay_range=search_params.get('delay_range', [1, 3])
        )
        
        task = ScrapingTask(
            task_id='',  # Will be auto-generated
            scraper_type=scraper_type,
            params=params,
            created_at='',  # Will be auto-generated
            timeout=search_params.get('timeout', 300),
            max_retries=search_params.get('max_retries', 3)
        )
        
        return task
    
    def submit_scraping_task(self, task: ScrapingTask) -> bool:
        """
        Submit a scraping task to the Go workers.
        
        Args:
            task: ScrapingTask to submit
            
        Returns:
            bool: True if submitted successfully
        """
        try:
            # Create database record
            with SessionLocal() as db:
                scraping_run = ScrapingRun(
                    source_site=task.scraper_type.value,
                    search_params={
                        'search_term': task.params.search_term,
                        'location': task.params.location,
                        'results_wanted': task.params.results_wanted,
                        'job_type': task.params.job_type,
                        'is_remote': task.params.is_remote
                    },
                    status='pending',
                    started_at=datetime.now(timezone.utc)
                )
                db.add(scraping_run)
                db.commit()
                
                # Update task with database ID
                task.task_id = f"{task.scraper_type.value}_{scraping_run.id}"
            
            # Submit to Redis queue
            success = self.message_protocol.publish_scraping_task(task)
            
            if success:
                self.logger.info(f"Submitted scraping task {task.task_id}")
            else:
                self.logger.error(f"Failed to submit scraping task {task.task_id}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error submitting scraping task: {e}")
            return False
    
    def process_scraping_results(self, timeout: int = 5) -> Optional[Dict]:
        """
        Process results from Go scrapers.
        
        Args:
            timeout: Timeout for getting results
            
        Returns:
            Dict with processing summary or None
        """
        try:
            result = self.message_protocol.get_scraping_result(timeout=timeout)
            if not result:
                return None
            
            self.logger.info(f"Processing result for task {result.task_id}")
            
            # Process the job data
            with SessionLocal() as db:
                # Update scraping run status
                site, run_id = result.task_id.split('_', 1)
                scraping_run = db.query(ScrapingRun).filter_by(id=int(run_id)).first()
                
                if scraping_run:
                    scraping_run.status = result.status.value
                    scraping_run.jobs_found = result.jobs_found
                    scraping_run.completed_at = datetime.fromisoformat(result.completed_at.replace('Z', '+00:00'))
                    scraping_run.error_message = result.error
                    
                    if result.metadata:
                        scraping_run.worker_id = result.metadata.worker_id
                
                # Process job data (will implement job deduplication later)
                jobs_processed = 0
                jobs_new = 0
                jobs_updated = 0
                
                for job_data in result.jobs_data:
                    # TODO: Implement job deduplication and database storage
                    # For now, just count the jobs
                    jobs_processed += 1
                    jobs_new += 1  # Temporary - will implement proper logic
                
                scraping_run.jobs_new = jobs_new
                scraping_run.jobs_updated = jobs_updated
                db.commit()
            
            summary = {
                'task_id': result.task_id,
                'status': result.status.value,
                'jobs_found': result.jobs_found,
                'jobs_processed': jobs_processed,
                'jobs_new': jobs_new,
                'jobs_updated': jobs_updated,
                'execution_time': result.execution_time,
                'scraper_type': result.scraper_type.value
            }
            
            self.logger.info(f"Processed result: {summary}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Error processing scraping results: {e}")
            return None
    
    def get_scraper_health(self, scraper_type: Optional[ScraperType] = None) -> List[Dict]:
        """
        Get health status of scrapers.
        
        Args:
            scraper_type: Optional filter by scraper type
            
        Returns:
            List of health status dictionaries
        """
        try:
            health_statuses = self.message_protocol.get_health_statuses(scraper_type)
            
            return [
                {
                    'worker_id': status.worker_id,
                    'scraper_type': status.scraper_type.value,
                    'status': status.status,
                    'active_tasks': status.active_tasks,
                    'completed_tasks_last_hour': status.completed_tasks_last_hour,
                    'error_rate_last_hour': status.error_rate_last_hour,
                    'memory_usage_mb': status.memory_usage_mb,
                    'cpu_usage_percent': status.cpu_usage_percent,
                    'proxy_pool_size': status.proxy_pool_size,
                    'proxy_success_rate': status.proxy_success_rate,
                    'last_successful_scrape': status.last_successful_scrape,
                    'timestamp': status.timestamp
                }
                for status in health_statuses
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting scraper health: {e}")
            return []
    
    def get_queue_status(self) -> Dict[str, int]:
        """
        Get status of scraping queues.
        
        Returns:
            Dict mapping scraper types to queue depths
        """
        try:
            return {
                scraper_type.value: self.message_protocol.get_queue_depth(scraper_type)
                for scraper_type in ScraperType
            }
        except Exception as e:
            self.logger.error(f"Error getting queue status: {e}")
            return {}


# Global orchestrator instance
orchestrator = ScrapingOrchestrator()


# Celery tasks
@celery_app.task(bind=True, name='app.workers.orchestrator.submit_scraping_job')
def submit_scraping_job(self: Task, scraper_type: str, search_params: Dict) -> Dict:
    """
    Celery task to submit a scraping job to Go workers.
    
    Args:
        scraper_type: Type of scraper (indeed, linkedin, etc.)
        search_params: Search parameters
        
    Returns:
        Dict with task submission result
    """
    try:
        logger.info(f"Submitting scraping job for {scraper_type}")
        
        # Create and submit task
        task = orchestrator.create_scraping_task(
            ScraperType(scraper_type), 
            search_params
        )
        
        success = orchestrator.submit_scraping_task(task)
        
        return {
            'success': success,
            'task_id': task.task_id,
            'scraper_type': scraper_type,
            'search_params': search_params,
            'submitted_at': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in submit_scraping_job: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name='app.workers.orchestrator.process_scraping_results')
def process_scraping_results(self: Task) -> Dict:
    """
    Celery task to process results from Go scrapers.
    
    Returns:
        Dict with processing summary
    """
    try:
        results_processed = 0
        total_jobs = 0
        
        # Process all available results
        while True:
            result = orchestrator.process_scraping_results(timeout=1)
            if not result:
                break
                
            results_processed += 1
            total_jobs += result['jobs_found']
        
        summary = {
            'results_processed': results_processed,
            'total_jobs': total_jobs,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }
        
        if results_processed > 0:
            logger.info(f"Processed {results_processed} results with {total_jobs} total jobs")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in process_scraping_results: {e}")
        raise self.retry(exc=e, countdown=30, max_retries=5)


@celery_app.task(name='app.workers.orchestrator.monitor_scraper_health')
def monitor_scraper_health() -> Dict:
    """
    Monitor health of Go scraper workers.
    
    Returns:
        Dict with health monitoring summary
    """
    try:
        health_statuses = orchestrator.get_scraper_health()
        queue_status = orchestrator.get_queue_status()
        
        # Check for unhealthy workers
        unhealthy_workers = [
            status for status in health_statuses 
            if status['status'] != 'healthy'
        ]
        
        # Check for backed up queues
        backed_up_queues = {
            scraper_type: depth 
            for scraper_type, depth in queue_status.items() 
            if depth > 100  # Threshold for "backed up"
        }
        
        summary = {
            'total_workers': len(health_statuses),
            'healthy_workers': len([s for s in health_statuses if s['status'] == 'healthy']),
            'unhealthy_workers': len(unhealthy_workers),
            'queue_status': queue_status,
            'backed_up_queues': backed_up_queues,
            'monitored_at': datetime.now(timezone.utc).isoformat()
        }
        
        if unhealthy_workers or backed_up_queues:
            logger.warning(f"Health issues detected: {summary}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in monitor_scraper_health: {e}")
        return {'error': str(e)}


@celery_app.task(name='app.workers.orchestrator.monitor_queue_health')
def monitor_queue_health() -> Dict:
    """
    Monitor queue health and auto-scale if needed.
    
    Returns:
        Dict with queue monitoring summary
    """
    try:
        queue_status = orchestrator.get_queue_status()
        health_statuses = orchestrator.get_scraper_health()
        
        # Group workers by type
        workers_by_type = {}
        for status in health_statuses:
            scraper_type = status['scraper_type']
            if scraper_type not in workers_by_type:
                workers_by_type[scraper_type] = []
            workers_by_type[scraper_type].append(status)
        
        recommendations = []
        
        for scraper_type, queue_depth in queue_status.items():
            active_workers = len(workers_by_type.get(scraper_type, []))
            
            # Recommend scaling up if queue is backed up
            if queue_depth > 50 and active_workers < 5:
                recommendations.append({
                    'action': 'scale_up',
                    'scraper_type': scraper_type,
                    'current_workers': active_workers,
                    'queue_depth': queue_depth,
                    'recommended_workers': min(active_workers + 2, 5)
                })
            
            # Recommend scaling down if queue is empty and many workers
            elif queue_depth == 0 and active_workers > 2:
                recommendations.append({
                    'action': 'scale_down',
                    'scraper_type': scraper_type,
                    'current_workers': active_workers,
                    'queue_depth': queue_depth,
                    'recommended_workers': max(active_workers - 1, 1)
                })
        
        return {
            'queue_status': queue_status,
            'workers_by_type': {k: len(v) for k, v in workers_by_type.items()},
            'recommendations': recommendations,
            'monitored_at': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in monitor_queue_health: {e}")
        return {'error': str(e)}