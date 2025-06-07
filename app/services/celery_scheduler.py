"""
Celery-based job scheduler - much simpler and more reliable than custom Redis scheduler.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.celery_app import celery_app
from app.tasks import execute_job_search


class CeleryScheduler:
    """Celery-based job scheduler"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def schedule_search(self, search_config: dict, schedule_time: Optional[datetime] = None) -> int:
        """Schedule a new search using Celery"""
        execution_time = schedule_time or datetime.now()
        
        # Create database record
        result = self.db.execute(text("""
            INSERT INTO scraping_runs (source_platform, search_terms, locations, 
                                     start_time, status, jobs_found, jobs_processed, 
                                     jobs_skipped, error_count, config_used)
            VALUES (:source_platform, ARRAY[:search_term], ARRAY[:location], :start_time, 
                    :status, :jobs_found, :jobs_processed, :jobs_skipped, 
                    :error_count, :config_used)
            RETURNING id
        """), {
            "source_platform": ",".join(search_config.get("site_names", ["indeed"])),
            "search_term": search_config.get("search_term", ""),
            "location": search_config.get("location", ""),
            "start_time": execution_time,
            "status": "pending",
            "jobs_found": 0,
            "jobs_processed": 0,
            "jobs_skipped": 0,
            "error_count": 0,
            "config_used": json.dumps(search_config, default=str)
        })
        
        search_id = result.fetchone()[0]
        self.db.commit()
        
        # Schedule with Celery
        if schedule_time and schedule_time > datetime.now():
            # Future execution
            task = execute_job_search.apply_async(
                args=[search_id, search_config],
                eta=schedule_time
            )
        else:
            # Immediate execution
            task = execute_job_search.delay(search_id, search_config)
        
        # Store task ID for potential cancellation by updating the config
        current_config = json.loads(search_config) if isinstance(search_config, str) else search_config.copy()
        current_config["celery_task_id"] = task.id
        
        # Convert datetime objects to strings for JSON serialization
        for key, value in current_config.items():
            if isinstance(value, datetime):
                current_config[key] = value.isoformat()
        
        self.db.execute(text("""
            UPDATE scraping_runs 
            SET config_used = :config_used
            WHERE id = :id
        """), {
            "id": search_id,
            "config_used": json.dumps(current_config, default=str)
        })
        self.db.commit()
        
        return search_id
    
    async def cancel_search(self, search_id: int) -> bool:
        """Cancel a pending search"""
        try:
            # Get the task ID
            result = self.db.execute(text("""
                SELECT config_used FROM scraping_runs 
                WHERE id = :id AND status IN ('pending', 'running')
            """), {"id": search_id})
            
            row = result.fetchone()
            if not row:
                return False
            
            config = json.loads(row.config_used) if row.config_used else {}
            task_id = config.get("celery_task_id")
            
            if task_id:
                # Revoke the Celery task
                celery_app.control.revoke(task_id, terminate=True)
            
            # Update database
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'cancelled', end_time = :end_time
                WHERE id = :id AND status IN ('pending', 'running')
            """), {"id": search_id, "end_time": datetime.now()})
            
            cancelled = self.db.commit()
            return True
            
        except Exception as e:
            print(f"Error cancelling search: {e}")
            return False
    
    async def get_scheduled_searches(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get list of scheduled searches from database"""
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
                    # Handle different config_used types (string or already parsed)
                    if isinstance(row.config_used, str):
                        config = json.loads(row.config_used)
                    elif isinstance(row.config_used, dict):
                        config = row.config_used
                    elif row.config_used:
                        config = json.loads(str(row.config_used))
                    else:
                        config = {}
                except (json.JSONDecodeError, TypeError, AttributeError):
                    config = {}
                
                searches.append({
                    "id": row.id,
                    "name": config.get("name", f"Search {row.id}"),
                    "search_term": config.get("search_term", ""),
                    "location": config.get("location", ""),
                    "site_names": config.get("site_names", []),
                    "status": row.status,
                    "jobs_found": row.jobs_found or 0,
                    "scheduled_time": row.start_time.isoformat() if row.start_time else None,
                    "completed_time": row.end_time.isoformat() if row.end_time else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "recurring": config.get("recurring", False),
                    "recurring_interval": config.get("recurring_interval"),
                    "search_params": config  # Include full config for API compatibility
                })
            
            return searches
            
        except Exception as e:
            print(f"Error getting scheduled searches: {e}")
            return []
    
    async def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler performance statistics"""
        try:
            # Get Celery stats
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            
            active_count = sum(len(tasks) for tasks in (active_tasks or {}).values())
            scheduled_count = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
            
            return {
                "pending_jobs": scheduled_count,
                "active_jobs": active_count,
                "scheduler_status": "running",
                "backend": "celery"
            }
            
        except Exception as e:
            print(f"Error getting scheduler stats: {e}")
            return {
                "pending_jobs": 0,
                "active_jobs": 0,
                "scheduler_status": "error",
                "backend": "celery"
            }


# Global scheduler instance
celery_scheduler_instance = None


async def get_celery_scheduler(db: Session) -> CeleryScheduler:
    """Get or create the global Celery scheduler instance"""
    global celery_scheduler_instance
    if celery_scheduler_instance is None:
        celery_scheduler_instance = CeleryScheduler(db)
    else:
        # Update the db session for this request
        celery_scheduler_instance.db = db
    return celery_scheduler_instance