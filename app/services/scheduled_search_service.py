"""
Scheduled search service for persistent testing across deployments.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.database import get_db
from app.models.scheduled_models import ScheduledSearch, TestRun, TestConfiguration
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class ScheduledSearchService:
    """Service for managing persistent scheduled searches."""
    
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
    
    def create_scheduled_search(
        self,
        name: str,
        search_term: str,
        location: str = None,
        site: str = "indeed",
        results_wanted: int = 10,
        frequency_hours: int = 24,
        description: str = None
    ) -> ScheduledSearch:
        """Create a new scheduled search for persistent testing."""
        
        # Calculate next run time
        next_run = datetime.utcnow() + timedelta(hours=frequency_hours)
        
        scheduled_search = ScheduledSearch(
            name=name,
            description=description,
            search_term=search_term,
            location=location,
            site=site,
            results_wanted=results_wanted,
            frequency_hours=frequency_hours,
            next_run_at=next_run,
            active=True
        )
        
        self.db.add(scheduled_search)
        self.db.commit()
        self.db.refresh(scheduled_search)
        
        logger.info(f"Created scheduled search: {name} - {search_term}")
        return scheduled_search
    
    def get_scheduled_searches(self, active_only: bool = True) -> List[ScheduledSearch]:
        """Get all scheduled searches."""
        query = self.db.query(ScheduledSearch)
        if active_only:
            query = query.filter(ScheduledSearch.active == True)
        return query.order_by(ScheduledSearch.created_at.desc()).all()
    
    def get_due_searches(self) -> List[ScheduledSearch]:
        """Get searches that are due to run."""
        now = datetime.utcnow()
        return self.db.query(ScheduledSearch).filter(
            and_(
                ScheduledSearch.active == True,
                or_(
                    ScheduledSearch.next_run_at <= now,
                    ScheduledSearch.next_run_at.is_(None)
                )
            )
        ).all()
    
    def execute_scheduled_search(self, scheduled_search: ScheduledSearch) -> TestRun:
        """Execute a scheduled search and record results."""
        start_time = datetime.utcnow()
        
        try:
            # Execute the job search
            search_params = {
                "search_term": scheduled_search.search_term,
                "location": scheduled_search.location,
                "site": scheduled_search.site,
                "results_wanted": scheduled_search.results_wanted
            }
            
            # Measure API response time
            api_start = datetime.utcnow()
            results = await JobService.search_jobs(search_params)
            api_end = datetime.utcnow()
            api_response_time = int((api_end - api_start).total_seconds() * 1000)
            
            # Calculate execution time
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Analyze results for duplicates (simplified)
            jobs_found = results.get("count", 0)
            cached_results = results.get("cached", False)
            
            # Create test run record
            test_run = TestRun(
                scheduled_search_id=scheduled_search.id,
                test_name=f"scheduled_{scheduled_search.name}",
                status="success",
                jobs_found=jobs_found,
                cached_results=cached_results,
                execution_time_ms=execution_time,
                api_response_time_ms=api_response_time,
                raw_results=results,
                server_version=self._get_server_version()
            )
            
            # Update scheduled search statistics
            scheduled_search.last_run_at = start_time
            scheduled_search.next_run_at = start_time + timedelta(hours=scheduled_search.frequency_hours)
            scheduled_search.total_runs += 1
            scheduled_search.total_jobs_found += jobs_found
            
            self.db.add(test_run)
            self.db.commit()
            self.db.refresh(test_run)
            
            logger.info(f"Executed scheduled search '{scheduled_search.name}': {jobs_found} jobs found")
            return test_run
            
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Record failed test run
            test_run = TestRun(
                scheduled_search_id=scheduled_search.id,
                test_name=f"scheduled_{scheduled_search.name}",
                status="failed",
                execution_time_ms=execution_time,
                error_message=str(e),
                server_version=self._get_server_version()
            )
            
            # Update next run time even on failure
            scheduled_search.last_run_at = start_time
            scheduled_search.next_run_at = start_time + timedelta(hours=scheduled_search.frequency_hours)
            scheduled_search.total_runs += 1
            
            self.db.add(test_run)
            self.db.commit()
            self.db.refresh(test_run)
            
            logger.error(f"Failed to execute scheduled search '{scheduled_search.name}': {str(e)}")
            return test_run
    
    def run_due_searches(self) -> List[TestRun]:
        """Run all searches that are due."""
        due_searches = self.get_due_searches()
        results = []
        
        for search in due_searches:
            test_run = self.execute_scheduled_search(search)
            results.append(test_run)
        
        return results
    
    def get_test_results(
        self,
        scheduled_search_id: int = None,
        limit: int = 100,
        status: str = None
    ) -> List[TestRun]:
        """Get test run results with optional filtering."""
        query = self.db.query(TestRun)
        
        if scheduled_search_id:
            query = query.filter(TestRun.scheduled_search_id == scheduled_search_id)
        
        if status:
            query = query.filter(TestRun.status == status)
        
        return query.order_by(TestRun.created_at.desc()).limit(limit).all()
    
    def get_test_statistics(self, scheduled_search_id: int = None) -> Dict[str, Any]:
        """Get comprehensive test statistics."""
        query = self.db.query(TestRun)
        
        if scheduled_search_id:
            query = query.filter(TestRun.scheduled_search_id == scheduled_search_id)
        
        test_runs = query.all()
        
        if not test_runs:
            return {"total_runs": 0, "success_rate": 0}
        
        total_runs = len(test_runs)
        successful_runs = len([r for r in test_runs if r.status == "success"])
        total_jobs = sum(r.jobs_found or 0 for r in test_runs)
        avg_execution_time = sum(r.execution_time_ms or 0 for r in test_runs) / total_runs
        
        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "success_rate": (successful_runs / total_runs) * 100,
            "total_jobs_found": total_jobs,
            "average_execution_time_ms": int(avg_execution_time),
            "last_run": test_runs[0].created_at if test_runs else None
        }
    
    def set_configuration(self, key: str, value: Any, description: str = None):
        """Set a persistent configuration value."""
        config = self.db.query(TestConfiguration).filter(TestConfiguration.key == key).first()
        
        if config:
            config.value = value
            config.description = description
            config.updated_at = datetime.utcnow()
        else:
            config = TestConfiguration(
                key=key,
                value=value,
                description=description
            )
            self.db.add(config)
        
        self.db.commit()
        return config
    
    def get_configuration(self, key: str, default: Any = None) -> Any:
        """Get a persistent configuration value."""
        config = self.db.query(TestConfiguration).filter(TestConfiguration.key == key).first()
        return config.value if config else default
    
    def _get_server_version(self) -> str:
        """Get current server version for tracking."""
        try:
            import json
            with open("/app/version.json", "r") as f:
                version_data = json.load(f)
                return f"{version_data.get('version', '1.0.0')}-{version_data.get('build_number', '0')}"
        except:
            return "unknown"