"""
Distributed job scheduler using Redis for high scalability.
Supports multiple API instances, precise timing, and job distribution.
"""
import json
import asyncio
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.job_service import JobService
from app.core.config import settings


class DistributedScheduler:
    """Redis-based distributed scheduler for job searches"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = None
        self._running = False
        self._worker_id = f"worker_{id(self)}"
        self._heartbeat_task = None
        self._scheduler_task = None
    
    async def start(self):
        """Start the distributed scheduler"""
        if self._running:
            return
            
        # Initialize Redis connection
        redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
        self.redis_client = redis.from_url(redis_url)
        
        self._running = True
        
        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        """Stop the distributed scheduler"""
        self._running = False
        
        # Cancel tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._scheduler_task:
            self._scheduler_task.cancel()
        
        # Clean up worker registration
        if self.redis_client:
            await self.redis_client.srem("scheduler:workers", self._worker_id)
            await self.redis_client.close()
    
    async def _heartbeat_loop(self):
        """Maintain worker heartbeat in Redis"""
        while self._running:
            try:
                # Register this worker with a TTL
                await self.redis_client.setex(
                    f"scheduler:worker:{self._worker_id}", 
                    60,  # 60 second TTL
                    json.dumps({"started": datetime.now().isoformat()})
                )
                await self.redis_client.sadd("scheduler:workers", self._worker_id)
                await asyncio.sleep(30)  # Refresh every 30 seconds
            except Exception as e:
                print(f"Heartbeat error: {e}")
                await asyncio.sleep(60)
    
    async def _scheduler_loop(self):
        """Main scheduler loop using Redis distributed coordination"""
        while self._running:
            try:
                # Check if this worker should process jobs (distributed locking)
                lock_acquired = await self._acquire_scheduler_lock()
                
                if lock_acquired:
                    await self._process_pending_jobs()
                    await self._release_scheduler_lock()
                
                await asyncio.sleep(10)  # Check every 10 seconds when active
                
            except Exception as e:
                print(f"Scheduler loop error: {e}")
                await asyncio.sleep(30)
    
    async def _acquire_scheduler_lock(self) -> bool:
        """Acquire distributed lock for job processing"""
        try:
            # Use Redis SET with NX (only if not exists) and EX (expiration)
            result = await self.redis_client.set(
                "scheduler:lock",
                self._worker_id,
                nx=True,  # Only set if key doesn't exist
                ex=30     # Expire after 30 seconds
            )
            return result is not None
        except Exception:
            return False
    
    async def _release_scheduler_lock(self):
        """Release distributed lock"""
        try:
            # Only release if this worker owns the lock
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await self.redis_client.eval(script, 1, "scheduler:lock", self._worker_id)
        except Exception:
            pass
    
    async def _process_pending_jobs(self):
        """Process all pending jobs that are due"""
        try:
            # Get jobs due for execution from Redis sorted set
            now = datetime.now().timestamp()
            
            # Get jobs that are due (score <= current timestamp)
            due_jobs = await self.redis_client.zrangebyscore(
                "scheduler:pending",
                0, now,
                start=0, num=10  # Process up to 10 jobs per cycle
            )
            
            for job_data in due_jobs:
                await self._execute_job(json.loads(job_data))
                # Remove from pending set
                await self.redis_client.zrem("scheduler:pending", job_data)
                
        except Exception as e:
            print(f"Error processing pending jobs: {e}")
    
    async def _execute_job(self, job_config: Dict[str, Any]):
        """Execute a single scheduled job"""
        try:
            search_id = job_config.get("search_id")
            
            # Update database status to running
            await self._update_search_status(search_id, "running")
            
            # Execute the job search
            search_params = job_config.get("search_params", {})
            jobs_df, _ = JobService.search_jobs({
                "site_name": search_params.get("site_names", ["indeed"]),
                "search_term": search_params.get("search_term"),
                "location": search_params.get("location"),
                "results_wanted": search_params.get("results_wanted", 20),
                "country_indeed": search_params.get("country_indeed", "USA")
            })
            
            jobs_found = len(jobs_df) if not jobs_df.empty else 0
            
            # Update with results
            await self._update_search_status(search_id, "completed", jobs_found)
            
            # Handle recurring jobs
            if search_params.get("recurring"):
                await self._schedule_next_occurrence(job_config)
                
            # Store job results in Redis for analytics
            await self._store_job_results(search_id, jobs_found, job_config)
            
        except Exception as e:
            # Mark as failed
            search_id = job_config.get("search_id")
            await self._update_search_status(search_id, "failed", error=str(e))
    
    async def _update_search_status(self, search_id: int, status: str, jobs_found: int = 0, error: str = None):
        """Update search status in database"""
        try:
            if status == "running":
                self.db.execute(text("""
                    UPDATE scraping_runs 
                    SET status = :status, start_time = :start_time
                    WHERE id = :id
                """), {"id": search_id, "status": status, "start_time": datetime.now()})
                
            elif status in ["completed", "failed"]:
                update_data = {
                    "id": search_id,
                    "status": status,
                    "end_time": datetime.now()
                }
                
                if status == "completed":
                    update_data["jobs_found"] = jobs_found
                    update_data["jobs_processed"] = jobs_found
                    
                if error:
                    update_data["error_details"] = json.dumps({"error": error})
                
                sql = """
                    UPDATE scraping_runs 
                    SET status = :status, end_time = :end_time
                """
                
                if status == "completed":
                    sql += ", jobs_found = :jobs_found, jobs_processed = :jobs_processed"
                    
                if error:
                    sql += ", error_details = :error_details"
                    
                sql += " WHERE id = :id"
                
                self.db.execute(text(sql), update_data)
            
            self.db.commit()
            
        except Exception as e:
            print(f"Error updating search status: {e}")
    
    async def _schedule_next_occurrence(self, job_config: Dict[str, Any]):
        """Schedule next occurrence of recurring job"""
        try:
            search_params = job_config.get("search_params", {})
            interval = search_params.get("recurring_interval", "daily")
            
            # Calculate next execution time
            if interval == "daily":
                next_time = datetime.now() + timedelta(days=1)
            elif interval == "weekly":
                next_time = datetime.now() + timedelta(weeks=1)
            elif interval == "monthly":
                next_time = datetime.now() + timedelta(days=30)
            else:
                return
            
            # Create new job config
            new_job_config = {
                **job_config,
                "scheduled_time": next_time.isoformat()
            }
            
            # Schedule in Redis
            await self.redis_client.zadd(
                "scheduler:pending",
                {json.dumps(new_job_config): next_time.timestamp()}
            )
            
        except Exception as e:
            print(f"Error scheduling next occurrence: {e}")
    
    async def _store_job_results(self, search_id: int, jobs_found: int, job_config: Dict[str, Any]):
        """Store job execution results for analytics"""
        try:
            result_data = {
                "search_id": search_id,
                "jobs_found": jobs_found,
                "executed_at": datetime.now().isoformat(),
                "search_params": job_config.get("search_params", {})
            }
            
            # Store in Redis list for recent results
            await self.redis_client.lpush(
                "scheduler:recent_results",
                json.dumps(result_data)
            )
            
            # Keep only last 100 results
            await self.redis_client.ltrim("scheduler:recent_results", 0, 99)
            
        except Exception as e:
            print(f"Error storing job results: {e}")
    
    async def schedule_search(self, search_config: dict, schedule_time: Optional[datetime] = None) -> int:
        """Schedule a new search"""
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
        
        # Schedule in Redis sorted set (score = execution timestamp)
        job_config = {
            "search_id": search_id,
            "search_params": search_config,
            "scheduled_time": execution_time.isoformat()
        }
        
        # Convert datetime objects to strings in search_config for JSON serialization
        serializable_config = {}
        for key, value in search_config.items():
            if isinstance(value, datetime):
                serializable_config[key] = value.isoformat()
            else:
                serializable_config[key] = value
        job_config["search_params"] = serializable_config
        
        await self.redis_client.zadd(
            "scheduler:pending",
            {json.dumps(job_config): execution_time.timestamp()}
        )
        
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
            
            if cancelled:
                # Remove from Redis queue
                # Note: This is a simplified approach; in production you'd want 
                # to implement more efficient search/removal
                all_jobs = await self.redis_client.zrange("scheduler:pending", 0, -1)
                for job_data in all_jobs:
                    job_config = json.loads(job_data)
                    if job_config.get("search_id") == search_id:
                        await self.redis_client.zrem("scheduler:pending", job_data)
                        break
            
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
        try:
            pending_count = await self.redis_client.zcard("scheduler:pending")
            active_workers = await self.redis_client.scard("scheduler:workers")
            recent_results = await self.redis_client.llen("scheduler:recent_results")
            
            return {
                "pending_jobs": pending_count,
                "active_workers": active_workers,
                "recent_executions": recent_results,
                "scheduler_status": "running" if self._running else "stopped"
            }
            
        except Exception as e:
            print(f"Error getting scheduler stats: {e}")
            return {
                "pending_jobs": 0,
                "active_workers": 0,
                "recent_executions": 0,
                "scheduler_status": "error"
            }


# Global distributed scheduler instance
distributed_scheduler_instance = None


async def get_distributed_scheduler(db: Session) -> DistributedScheduler:
    """Get or create the global distributed scheduler instance"""
    global distributed_scheduler_instance
    if distributed_scheduler_instance is None:
        distributed_scheduler_instance = DistributedScheduler(db)
        await distributed_scheduler_instance.start()
    else:
        # Update the db session for this request
        distributed_scheduler_instance.db = db
    return distributed_scheduler_instance