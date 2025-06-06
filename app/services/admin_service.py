import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.admin_models import (
    ScheduledSearchRequest, ScheduledSearchResponse, AdminStats,
    SearchTemplate, SearchLog, SearchStatus
)
from app.cache import cache


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self._search_store = {}  # In-memory store for demo, use DB in production
        self._template_store = {}
        self._log_store = []

    async def get_admin_stats(self) -> AdminStats:
        """Get admin dashboard statistics"""
        # In production, these would come from the database
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Mock data for now - replace with actual DB queries
        total_searches = len(self._search_store)
        searches_today = len([s for s in self._search_store.values() if s.created_at >= today_start])
        active_searches = len([s for s in self._search_store.values() if s.status == SearchStatus.RUNNING])
        failed_searches_today = len([s for s in self._search_store.values() 
                                   if s.status == SearchStatus.FAILED and s.created_at >= today_start])
        
        # Calculate jobs found (mock data)
        total_jobs = sum(s.jobs_found or 0 for s in self._search_store.values())
        jobs_today = sum(s.jobs_found or 0 for s in self._search_store.values() 
                        if s.created_at >= today_start)
        
        return AdminStats(
            total_searches=total_searches,
            searches_today=searches_today,
            total_jobs_found=total_jobs,
            jobs_found_today=jobs_today,
            active_searches=active_searches,
            failed_searches_today=failed_searches_today,
            cache_hit_rate=0.85,  # Mock cache hit rate
            system_health={
                "status": "healthy",
                "database": "connected",
                "redis": "connected",
                "memory_usage": "45%",
                "cpu_usage": "23%"
            }
        )

    async def create_scheduled_search(self, search_id: str, request: ScheduledSearchRequest) -> ScheduledSearchResponse:
        """Create a new scheduled search"""
        search_record = ScheduledSearchResponse(
            id=search_id,
            name=request.name,
            status=SearchStatus.PENDING,
            search_params=request.dict(),
            created_at=datetime.now(),
            scheduled_time=request.schedule_time,
            started_at=None,
            completed_at=None,
            jobs_found=None,
            error_message=None,
            recurring=request.recurring,
            recurring_interval=request.recurring_interval,
            next_run=request.schedule_time if request.schedule_time else datetime.now()
        )
        
        self._search_store[search_id] = search_record
        return search_record

    async def get_scheduled_searches(self, status: Optional[SearchStatus] = None, limit: int = 50) -> List[ScheduledSearchResponse]:
        """Get list of scheduled searches"""
        searches = list(self._search_store.values())
        
        if status:
            searches = [s for s in searches if s.status == status]
        
        # Sort by created_at descending
        searches.sort(key=lambda x: x.created_at, reverse=True)
        
        return searches[:limit]

    async def get_search_by_id(self, search_id: str) -> Optional[ScheduledSearchResponse]:
        """Get search by ID"""
        return self._search_store.get(search_id)

    async def cancel_search(self, search_id: str) -> bool:
        """Cancel a scheduled search"""
        search = self._search_store.get(search_id)
        if not search:
            return False
        
        if search.status in [SearchStatus.PENDING, SearchStatus.RUNNING]:
            search.status = SearchStatus.CANCELLED
            search.completed_at = datetime.now()
            return True
        
        return False

    async def update_search_status(self, search_id: str, status: SearchStatus, 
                                 jobs_found: Optional[int] = None, 
                                 error_message: Optional[str] = None):
        """Update search status"""
        search = self._search_store.get(search_id)
        if search:
            search.status = status
            if status == SearchStatus.RUNNING and not search.started_at:
                search.started_at = datetime.now()
            elif status in [SearchStatus.COMPLETED, SearchStatus.FAILED, SearchStatus.CANCELLED]:
                search.completed_at = datetime.now()
            
            if jobs_found is not None:
                search.jobs_found = jobs_found
            if error_message:
                search.error_message = error_message

    async def get_search_templates(self) -> List[SearchTemplate]:
        """Get all search templates"""
        return list(self._template_store.values())

    async def create_search_template(self, template: SearchTemplate) -> SearchTemplate:
        """Create a new search template"""
        template.id = str(uuid.uuid4())
        template.created_at = datetime.now()
        template.updated_at = datetime.now()
        
        self._template_store[template.id] = template
        return template

    async def get_search_logs(self, search_id: Optional[str] = None, 
                            level: Optional[str] = None, 
                            limit: int = 100) -> List[SearchLog]:
        """Get search logs"""
        logs = self._log_store.copy()
        
        if search_id:
            logs = [log for log in logs if log.search_id == search_id]
        
        if level:
            logs = [log for log in logs if log.level == level.upper()]
        
        # Sort by timestamp descending
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        return logs[:limit]

    async def add_search_log(self, search_id: str, level: str, message: str, details: Optional[Dict] = None):
        """Add a search log entry"""
        log_entry = SearchLog(
            id=str(uuid.uuid4()),
            search_id=search_id,
            level=level.upper(),
            message=message,
            timestamp=datetime.now(),
            details=details
        )
        
        self._log_store.append(log_entry)
        
        # Keep only last 1000 logs to prevent memory issues
        if len(self._log_store) > 1000:
            self._log_store = self._log_store[-1000:]

    async def schedule_search_task(self, search_id: str, schedule_time: datetime, search_params: Dict):
        """Schedule a search task for later execution"""
        # In production, this would use Celery or similar task queue
        # For now, we'll just update the search record
        search = self._search_store.get(search_id)
        if search:
            search.scheduled_time = schedule_time
            search.next_run = schedule_time

    async def get_system_health(self) -> Dict[str, Any]:
        """Get detailed system health information"""
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "components": {
                "database": {
                    "status": "connected",
                    "response_time_ms": 5
                },
                "redis": {
                    "status": "connected", 
                    "response_time_ms": 2
                },
                "job_sites": {
                    "indeed": "accessible",
                    "linkedin": "accessible", 
                    "glassdoor": "accessible"
                }
            },
            "performance": {
                "memory_usage_percent": 45,
                "cpu_usage_percent": 23,
                "disk_usage_percent": 12
            },
            "searches": {
                "active_count": len([s for s in self._search_store.values() if s.status == SearchStatus.RUNNING]),
                "pending_count": len([s for s in self._search_store.values() if s.status == SearchStatus.PENDING]),
                "completed_today": len([s for s in self._search_store.values() 
                                     if s.status == SearchStatus.COMPLETED and 
                                     s.completed_at and s.completed_at.date() == datetime.now().date()])
            }
        }