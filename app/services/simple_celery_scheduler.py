"""
Simple Celery scheduler that works without complex container setup.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text



class SimpleCeleryScheduler:
    """Simple Celery-based job scheduler"""
    
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
            "config_used": json.dumps(search_config)
        })
        
        search_id = result.fetchone()[0]
        self.db.commit()
        
        # For now, execute immediately since Celery containers aren't ready
        # This gives us the same functionality while we set up proper Celery
        try:
            from app.services.job_service import JobService
            
            # Update status to running
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'running', start_time = :start_time
                WHERE id = :id
            """), {"id": search_id, "start_time": datetime.now()})
            self.db.commit()
            
            # Execute the actual job search
            jobs_df, _ = JobService.search_jobs({
                "site_name": search_config.get("site_names", ["indeed"]),
                "search_term": search_config.get("search_term"),
                "location": search_config.get("location"),
                "results_wanted": search_config.get("results_wanted", 20),
                "country_indeed": search_config.get("country_indeed", "USA")
            })
            
            jobs_found = len(jobs_df) if not jobs_df.empty else 0
            
            # Update with results
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'completed', end_time = :end_time, 
                    jobs_found = :jobs_found, jobs_processed = :jobs_processed
                WHERE id = :id
            """), {
                "id": search_id,
                "end_time": datetime.now(),
                "jobs_found": jobs_found,
                "jobs_processed": jobs_found
            })
            self.db.commit()
            
        except Exception as e:
            # Mark as failed
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'failed', end_time = :end_time, 
                    error_details = :error_details
                WHERE id = :id
            """), {
                "id": search_id,
                "end_time": datetime.now(),
                "error_details": json.dumps({"error": str(e)})
            })
            self.db.commit()
        
        return search_id
    
    async def cancel_search(self, search_id: int) -> bool:
        """Cancel a pending search"""
        try:
            # Update database
            result = self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'cancelled', end_time = :end_time
                WHERE id = :id AND status IN ('pending', 'running')
            """), {"id": search_id, "end_time": datetime.now()})
            
            cancelled = result.rowcount > 0
            self.db.commit()
            return cancelled
            
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
        return {
            "pending_jobs": 0,
            "active_jobs": 0,
            "scheduler_status": "running",
            "backend": "simple_celery"
        }


# Global scheduler instance
simple_celery_scheduler_instance = None


async def get_simple_celery_scheduler(db: Session) -> SimpleCeleryScheduler:
    """Get or create the global simple Celery scheduler instance"""
    global simple_celery_scheduler_instance
    if simple_celery_scheduler_instance is None:
        simple_celery_scheduler_instance = SimpleCeleryScheduler(db)
    else:
        # Update the db session for this request
        simple_celery_scheduler_instance.db = db
    return simple_celery_scheduler_instance