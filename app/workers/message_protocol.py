"""
Redis message protocol for Python-Go communication.
Provides a standardized way for Python orchestrator and Go scrapers to communicate.
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.cache_backend import cache_backend

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    RETRY = "retry"


class ScraperType(Enum):
    """Supported scraper types."""
    INDEED = "indeed"
    LINKEDIN = "linkedin"
    GLASSDOOR = "glassdoor"
    ZIPRECRUITER = "ziprecruiter"
    GOOGLE = "google"


@dataclass
class ScrapingTaskParams:
    """Parameters for a scraping task."""
    search_term: str
    location: str
    results_wanted: int = 50
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    is_remote: Optional[bool] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    delay_range: List[int] = None
    page_limit: int = 5
    
    def __post_init__(self):
        if self.delay_range is None:
            self.delay_range = [1, 3]


@dataclass
class ScrapingTask:
    """A scraping task message."""
    task_id: str
    scraper_type: ScraperType
    params: ScrapingTaskParams
    created_at: str
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 1
    
    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class JobData:
    """Individual job data from scraping."""
    title: str
    company: str
    location: str
    job_url: str
    description: str
    posted_date: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    is_remote: bool = False
    apply_url: Optional[str] = None
    easy_apply: bool = False
    company_logo: Optional[str] = None
    job_hash: Optional[str] = None
    external_job_id: Optional[str] = None
    
    # Additional metadata
    skills: List[str] = None
    benefits: List[str] = None
    requirements: Optional[str] = None
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.benefits is None:
            self.benefits = []


@dataclass
class ScrapingMetadata:
    """Metadata about the scraping execution."""
    proxy_used: Optional[str] = None
    user_agent_used: Optional[str] = None
    requests_made: int = 0
    pages_scraped: int = 0
    rate_limited: bool = False
    captcha_encountered: bool = False
    blocked_requests: int = 0
    average_response_time: float = 0.0
    memory_usage_mb: float = 0.0
    worker_id: Optional[str] = None


@dataclass
class ScrapingResult:
    """Result message from a scraping task."""
    task_id: str
    status: TaskStatus
    scraper_type: ScraperType
    execution_time: float
    jobs_found: int
    jobs_data: List[JobData]
    metadata: ScrapingMetadata
    completed_at: str
    error: Optional[str] = None
    
    def __post_init__(self):
        if not self.completed_at:
            self.completed_at = datetime.now(timezone.utc).isoformat()


@dataclass
class HealthStatus:
    """Health status message from scrapers."""
    worker_id: str
    scraper_type: ScraperType
    status: str  # healthy, degraded, unhealthy
    active_tasks: int
    completed_tasks_last_hour: int
    error_rate_last_hour: float
    memory_usage_mb: float
    cpu_usage_percent: float
    proxy_pool_size: int
    proxy_success_rate: float
    last_successful_scrape: str
    timestamp: str
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class MessageProtocol:
    """Handles Redis communication between Python and Go components."""
    
    # Redis channel names
    CHANNELS = {
        'scraping_tasks': 'scraping:tasks',
        'scraping_results': 'scraping:results',
        'health_monitoring': 'scrapers:health',
        'error_reporting': 'scrapers:errors',
        'worker_commands': 'scrapers:commands'
    }
    
    def __init__(self, redis_backend=None):
        """Initialize message protocol with Redis backend."""
        self.redis = redis_backend or cache_backend
        self.logger = logging.getLogger(f"{__name__}.MessageProtocol")
    
    def publish_scraping_task(self, task: ScrapingTask) -> bool:
        """
        Publish a scraping task to the queue.
        
        Args:
            task: ScrapingTask instance
            
        Returns:
            bool: True if published successfully
        """
        try:
            # Convert to dictionary and handle enums
            task_dict = asdict(task)
            task_dict['scraper_type'] = task.scraper_type.value
            
            # Serialize to JSON
            message = json.dumps(task_dict, default=str)
            
            # Publish to Redis channel
            channel = self.CHANNELS['scraping_tasks']
            result = self.redis.client.lpush(f"{channel}:{task.scraper_type.value}", message)
            
            self.logger.info(f"Published task {task.task_id} to {channel}:{task.scraper_type.value}")
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"Failed to publish scraping task {task.task_id}: {e}")
            return False
    
    def get_scraping_task(self, scraper_type: ScraperType, timeout: int = 30) -> Optional[ScrapingTask]:
        """
        Get a scraping task from the queue (blocking).
        
        Args:
            scraper_type: Type of scraper requesting tasks
            timeout: Timeout in seconds
            
        Returns:
            ScrapingTask instance or None
        """
        try:
            channel = f"{self.CHANNELS['scraping_tasks']}:{scraper_type.value}"
            result = self.redis.client.brpop(channel, timeout=timeout)
            
            if not result:
                return None
                
            # Parse JSON message
            _, message = result
            task_dict = json.loads(message)
            
            # Convert back to objects
            params = ScrapingTaskParams(**task_dict['params'])
            task = ScrapingTask(
                task_id=task_dict['task_id'],
                scraper_type=ScraperType(task_dict['scraper_type']),
                params=params,
                created_at=task_dict['created_at'],
                timeout=task_dict['timeout'],
                retry_count=task_dict['retry_count'],
                max_retries=task_dict['max_retries'],
                priority=task_dict.get('priority', 1)
            )
            
            self.logger.info(f"Retrieved task {task.task_id} from {channel}")
            return task
            
        except Exception as e:
            self.logger.error(f"Failed to get scraping task: {e}")
            return None
    
    def publish_scraping_result(self, result: ScrapingResult) -> bool:
        """
        Publish scraping results.
        
        Args:
            result: ScrapingResult instance
            
        Returns:
            bool: True if published successfully
        """
        try:
            # Convert to dictionary
            result_dict = asdict(result)
            result_dict['status'] = result.status.value
            result_dict['scraper_type'] = result.scraper_type.value
            
            # Serialize to JSON
            message = json.dumps(result_dict, default=str)
            
            # Publish to results channel
            channel = self.CHANNELS['scraping_results']
            result_published = self.redis.client.lpush(channel, message)
            
            self.logger.info(f"Published result for task {result.task_id}")
            return bool(result_published)
            
        except Exception as e:
            self.logger.error(f"Failed to publish scraping result {result.task_id}: {e}")
            return False
    
    def get_scraping_result(self, timeout: int = 5) -> Optional[ScrapingResult]:
        """
        Get scraping results (non-blocking by default).
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            ScrapingResult instance or None
        """
        try:
            channel = self.CHANNELS['scraping_results']
            result = self.redis.client.brpop(channel, timeout=timeout)
            
            if not result:
                return None
                
            # Parse JSON message
            _, message = result
            result_dict = json.loads(message)
            
            # Convert back to objects
            jobs_data = [JobData(**job) for job in result_dict['jobs_data']]
            metadata = ScrapingMetadata(**result_dict['metadata'])
            
            scraping_result = ScrapingResult(
                task_id=result_dict['task_id'],
                status=TaskStatus(result_dict['status']),
                scraper_type=ScraperType(result_dict['scraper_type']),
                execution_time=result_dict['execution_time'],
                jobs_found=result_dict['jobs_found'],
                jobs_data=jobs_data,
                metadata=metadata,
                completed_at=result_dict['completed_at'],
                error=result_dict.get('error')
            )
            
            self.logger.info(f"Retrieved result for task {scraping_result.task_id}")
            return scraping_result
            
        except Exception as e:
            self.logger.error(f"Failed to get scraping result: {e}")
            return None
    
    def publish_health_status(self, health: HealthStatus) -> bool:
        """
        Publish health status from scrapers.
        
        Args:
            health: HealthStatus instance
            
        Returns:
            bool: True if published successfully
        """
        try:
            # Convert to dictionary
            health_dict = asdict(health)
            health_dict['scraper_type'] = health.scraper_type.value
            
            # Serialize to JSON
            message = json.dumps(health_dict, default=str)
            
            # Publish to health channel with TTL
            channel = f"{self.CHANNELS['health_monitoring']}:{health.scraper_type.value}"
            self.redis.set(f"{channel}:{health.worker_id}", message, ttl=120)  # 2 minute TTL
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to publish health status: {e}")
            return False
    
    def get_health_statuses(self, scraper_type: Optional[ScraperType] = None) -> List[HealthStatus]:
        """
        Get health statuses for scrapers.
        
        Args:
            scraper_type: Optional filter by scraper type
            
        Returns:
            List of HealthStatus instances
        """
        try:
            health_statuses = []
            
            if scraper_type:
                pattern = f"{self.CHANNELS['health_monitoring']}:{scraper_type.value}:*"
            else:
                pattern = f"{self.CHANNELS['health_monitoring']}:*"
                
            # Get all health status keys
            keys = self.redis.client.keys(pattern)
            
            for key in keys:
                message = self.redis.get(key.decode() if isinstance(key, bytes) else key)
                if message:
                    health_dict = json.loads(message)
                    health = HealthStatus(
                        worker_id=health_dict['worker_id'],
                        scraper_type=ScraperType(health_dict['scraper_type']),
                        status=health_dict['status'],
                        active_tasks=health_dict['active_tasks'],
                        completed_tasks_last_hour=health_dict['completed_tasks_last_hour'],
                        error_rate_last_hour=health_dict['error_rate_last_hour'],
                        memory_usage_mb=health_dict['memory_usage_mb'],
                        cpu_usage_percent=health_dict['cpu_usage_percent'],
                        proxy_pool_size=health_dict['proxy_pool_size'],
                        proxy_success_rate=health_dict['proxy_success_rate'],
                        last_successful_scrape=health_dict['last_successful_scrape'],
                        timestamp=health_dict['timestamp']
                    )
                    health_statuses.append(health)
            
            return health_statuses
            
        except Exception as e:
            self.logger.error(f"Failed to get health statuses: {e}")
            return []
    
    def publish_error(self, task_id: str, scraper_type: ScraperType, error: str, 
                     metadata: Optional[Dict] = None) -> bool:
        """
        Publish error information.
        
        Args:
            task_id: Task ID that failed
            scraper_type: Type of scraper
            error: Error message
            metadata: Additional error metadata
            
        Returns:
            bool: True if published successfully
        """
        try:
            error_data = {
                'task_id': task_id,
                'scraper_type': scraper_type.value,
                'error': error,
                'metadata': metadata or {},
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            message = json.dumps(error_data, default=str)
            channel = self.CHANNELS['error_reporting']
            
            result = self.redis.client.lpush(channel, message)
            self.logger.info(f"Published error for task {task_id}")
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"Failed to publish error: {e}")
            return False
    
    def get_queue_depth(self, scraper_type: ScraperType) -> int:
        """
        Get the number of pending tasks for a scraper type.
        
        Args:
            scraper_type: Type of scraper
            
        Returns:
            int: Number of pending tasks
        """
        try:
            channel = f"{self.CHANNELS['scraping_tasks']}:{scraper_type.value}"
            return self.redis.client.llen(channel)
        except Exception as e:
            self.logger.error(f"Failed to get queue depth: {e}")
            return 0
    
    def clear_queue(self, scraper_type: ScraperType) -> bool:
        """
        Clear all pending tasks for a scraper type.
        
        Args:
            scraper_type: Type of scraper
            
        Returns:
            bool: True if cleared successfully
        """
        try:
            channel = f"{self.CHANNELS['scraping_tasks']}:{scraper_type.value}"
            self.redis.client.delete(channel)
            self.logger.info(f"Cleared queue for {scraper_type.value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear queue: {e}")
            return False


# Global instance
message_protocol = MessageProtocol()