"""
Job search scheduler service for handling delayed and recurring searches.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.job_service import JobService
from app.models.admin_models import SearchStatus


class SchedulerService:
    """Service for managing scheduled job searches"""
    
    def __init__(self, db: Session):
        self.db = db
        self._running = False
        self._task = None
    
    async def start(self):
        """Start the scheduler background task"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        """Stop the scheduler background task"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _scheduler_loop(self):
        """Main scheduler loop that checks for pending searches"""
        while self._running:
            try:
                await self._process_pending_searches()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _process_pending_searches(self):
        """Process all pending scheduled searches that are due"""
        try:
            # Get pending searches that are due
            sql = """
                SELECT id, source_platform, search_terms, locations, start_time, 
                       status, config_used, created_at
                FROM scraping_runs 
                WHERE status = 'pending' 
                AND start_time <= :now
                ORDER BY start_time ASC
                LIMIT 10
            """
            result = self.db.execute(text(sql), {"now": datetime.now()})
            pending_searches = result.fetchall()
            
            for search in pending_searches:
                await self._execute_scheduled_search(search)
                
        except Exception as e:
            print(f"Error processing pending searches: {e}")
    
    async def _execute_scheduled_search(self, search_row):
        """Execute a single scheduled search"""
        try:
            # Update status to running
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'running', start_time = :now
                WHERE id = :id
            """), {"id": search_row.id, "now": datetime.now()})
            self.db.commit()
            
            # Parse search configuration
            config = json.loads(search_row.config_used) if search_row.config_used else {}
            
            # Execute the actual job search
            jobs_df, _ = JobService.search_jobs({
                "site_name": config.get("site_names", ["indeed"]),
                "search_term": config.get("search_term"),
                "location": config.get("location"),
                "results_wanted": config.get("results_wanted", 20),
                "country_indeed": config.get("country_indeed", "USA")
            })
            
            jobs_found = len(jobs_df) if not jobs_df.empty else 0
            
            # Update with results
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'completed', end_time = :end_time, 
                    jobs_found = :jobs_found, jobs_processed = :jobs_processed
                WHERE id = :id
            """), {
                "id": search_row.id,
                "end_time": datetime.now(),
                "jobs_found": jobs_found,
                "jobs_processed": jobs_found
            })
            self.db.commit()
            
            # Handle recurring searches
            if config.get("recurring"):
                await self._schedule_next_occurrence(search_row, config)
                
        except Exception as e:
            # Mark as failed
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'failed', end_time = :end_time, 
                    error_details = :error_details
                WHERE id = :id
            """), {
                "id": search_row.id,
                "end_time": datetime.now(),
                "error_details": json.dumps({"error": str(e)})
            })
            self.db.commit()
    
    async def _schedule_next_occurrence(self, search_row, config):
        """Schedule the next occurrence of a recurring search"""
        try:
            interval = config.get("recurring_interval", "daily")
            current_time = search_row.start_time or datetime.now()
            
            # Calculate next run time
            if interval == "daily":
                next_time = current_time + timedelta(days=1)
            elif interval == "weekly":
                next_time = current_time + timedelta(weeks=1)
            elif interval == "monthly":
                next_time = current_time + timedelta(days=30)
            else:
                return  # Unknown interval
            
            # Create new scheduled search
            self.db.execute(text("""
                INSERT INTO scraping_runs (source_platform, search_terms, locations, 
                                         start_time, status, jobs_found, jobs_processed, 
                                         jobs_skipped, error_count, config_used)
                VALUES (:source_platform, :search_terms, :locations, :start_time, 
                        :status, :jobs_found, :jobs_processed, :jobs_skipped, 
                        :error_count, :config_used)
            """), {
                "source_platform": search_row.source_platform,
                "search_terms": search_row.search_terms,
                "locations": search_row.locations,
                "start_time": next_time,
                "status": "pending",
                "jobs_found": 0,
                "jobs_processed": 0,
                "jobs_skipped": 0,
                "error_count": 0,
                "config_used": search_row.config_used
            })
            self.db.commit()
            
        except Exception as e:
            print(f"Error scheduling next occurrence: {e}")
    
    async def schedule_search(self, search_config: dict, schedule_time: Optional[datetime] = None) -> int:
        """Schedule a new search for future execution"""
        execution_time = schedule_time or datetime.now()
        status = "pending" if schedule_time and schedule_time > datetime.now() else "pending"
        
        result = self.db.execute(text("""
            INSERT INTO scraping_runs (source_platform, search_terms, locations, 
                                     start_time, status, jobs_found, jobs_processed, 
                                     jobs_skipped, error_count, config_used)
            VALUES (:source_platform, :search_terms, :locations, :start_time, 
                    :status, :jobs_found, :jobs_processed, :jobs_skipped, 
                    :error_count, :config_used)
            RETURNING id
        """), {
            "source_platform": ",".join(search_config.get("site_names", ["indeed"])),
            "search_terms": [search_config.get("search_term", "")],
            "locations": [search_config.get("location", "")],
            "start_time": execution_time,
            "status": status,
            "jobs_found": 0,
            "jobs_processed": 0,
            "jobs_skipped": 0,
            "error_count": 0,
            "config_used": json.dumps(search_config)
        })
        
        search_id = result.fetchone()[0]
        self.db.commit()
        return search_id
    
    async def cancel_search(self, search_id: int) -> bool:
        """Cancel a pending scheduled search"""
        try:
            result = self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'cancelled', end_time = :end_time
                WHERE id = :id AND status IN ('pending', 'running')
            """), {"id": search_id, "end_time": datetime.now()})
            
            cancelled = result.rowcount > 0
            self.db.commit()
            return cancelled
            
        except Exception:
            return False
    
    async def get_scheduled_searches(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get list of scheduled searches"""
        try:
            where_clause = "WHERE status = :status" if status else ""
            params = {"limit": limit}
            if status:
                params["status"] = status
            
            sql = f"""
                SELECT id, source_platform, search_terms, locations, start_time, end_time,
                       status, jobs_found, config_used, created_at
                FROM scraping_runs 
                {where_clause}
                ORDER BY start_time DESC 
                LIMIT :limit
            """
            
            result = self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            searches = []
            for row in rows:
                try:
                    config = json.loads(row.config_used) if row.config_used else {}
                except (json.JSONDecodeError, TypeError):
                    config = {}
                
                searches.append({
                    "id": row.id,
                    "name": config.get("name", f"Search {row.id}"),
                    "search_term": config.get("search_term", ""),
                    "location": config.get("location", ""),
                    "site_names": config.get("site_names", []),
                    "status": row.status,
                    "jobs_found": row.jobs_found,
                    "scheduled_time": row.start_time.isoformat() if row.start_time else None,
                    "completed_time": row.end_time.isoformat() if row.end_time else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "recurring": config.get("recurring", False),
                    "recurring_interval": config.get("recurring_interval")
                })
            
            return searches
            
        except Exception as e:
            print(f"Error getting scheduled searches: {e}")
            return []


# Global scheduler instance
scheduler_instance = None


async def get_scheduler(db: Session) -> SchedulerService:
    """Get or create the global scheduler instance"""
    global scheduler_instance
    if scheduler_instance is None:
        scheduler_instance = SchedulerService(db)
        await scheduler_instance.start()
    return scheduler_instance