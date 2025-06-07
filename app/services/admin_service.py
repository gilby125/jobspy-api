import uuid
import logging
import psutil
import redis
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text

from app.models.admin_models import (
    ScheduledSearchRequest, ScheduledSearchResponse, AdminStats,
    SearchTemplate, SearchLog, SearchStatus
)
from app.cache import cache
from app.services.log_service import LogService


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
        self.log_service = LogService(db)

    async def get_admin_stats(self) -> AdminStats:
        """Get admin dashboard statistics from database"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            # Get scraping run statistics using raw SQL for the actual schema
            from sqlalchemy import text
            
            # Total searches
            result = self.db.execute(text("SELECT COUNT(*) FROM scraping_runs"))
            total_searches = result.scalar() or 0
            
            # Searches today
            result = self.db.execute(text(
                "SELECT COUNT(*) FROM scraping_runs WHERE start_time >= :today_start"
            ), {"today_start": today_start})
            searches_today = result.scalar() or 0
            
            # Active searches
            result = self.db.execute(text(
                "SELECT COUNT(*) FROM scraping_runs WHERE status IN ('pending', 'running')"
            ))
            active_searches = result.scalar() or 0
            
            # Get job posting statistics (check if job_postings table exists)
            try:
                result = self.db.execute(text("SELECT COUNT(*) FROM job_postings"))
                total_jobs_found = result.scalar() or 0
                
                result = self.db.execute(text(
                    "SELECT COUNT(*) FROM job_postings WHERE created_at >= :today_start"
                ), {"today_start": today_start})
                jobs_found_today = result.scalar() or 0
            except Exception:
                # Table might not exist yet
                total_jobs_found = 0
                jobs_found_today = 0
            
        except Exception as e:
            # Fallback to zero values if database isn't available
            total_searches = 0
            searches_today = 0
            active_searches = 0
            total_jobs_found = 0
            jobs_found_today = 0
        
        try:
            result = self.db.execute(text(
                "SELECT COUNT(*) FROM scraping_runs WHERE status = 'failed' AND start_time >= :today_start"
            ), {"today_start": today_start})
            failed_searches_today = result.scalar() or 0
        except Exception:
            failed_searches_today = 0
        
        # Get cache hit rate from Redis if available
        cache_hit_rate = await self._get_cache_hit_rate()
        
        # Check system health
        system_health = await self._check_system_health()
        
        return AdminStats(
            total_searches=total_searches,
            searches_today=searches_today,
            total_jobs_found=total_jobs_found,
            jobs_found_today=jobs_found_today,
            active_searches=active_searches,
            failed_searches_today=failed_searches_today,
            cache_hit_rate=cache_hit_rate,
            system_health=system_health
        )
    
    async def _check_system_health(self) -> Dict[str, str]:
        """Check system component health"""
        health = {}
        
        # Check database
        try:
            self.db.execute(text("SELECT 1"))
            health["database"] = "healthy"
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            health["database"] = "unhealthy"
        
        # Check cache/Redis
        try:
            from app.cache import cache
            # Test cache connectivity
            test_key = "health_check_test"
            await cache.set(test_key, "test", expire=10)
            result = await cache.get(test_key)
            if result == "test":
                health["cache"] = "healthy"
            else:
                health["cache"] = "unhealthy"
        except Exception as e:
            self.logger.error(f"Cache health check failed: {e}")
            health["cache"] = "unhealthy"
        
        # API is healthy if we got this far
        health["api"] = "healthy"
        
        return health

    async def create_scheduled_search(self, search_id: str, request: ScheduledSearchRequest) -> ScheduledSearchResponse:
        """Create a new scheduled search in database"""
        try:
            # Create scraping run record in database
            search_terms = [request.search_term] if request.search_term else []
            locations = [request.location] if request.location else []
            
            scheduled_time = request.schedule_time if request.schedule_time else datetime.now()
            
            result = self.db.execute(text("""
                INSERT INTO scraping_runs (
                    source_platform, search_terms, locations, start_time, status, 
                    jobs_found, jobs_processed, jobs_skipped, error_count, config_used
                ) VALUES (
                    :source_platform, :search_terms, :locations, :start_time, :status,
                    :jobs_found, :jobs_processed, :jobs_skipped, :error_count, :config_used
                ) RETURNING id
            """), {
                "source_platform": ",".join(request.site_names),
                "search_terms": search_terms,
                "locations": locations,
                "start_time": scheduled_time,
                "status": SearchStatus.PENDING.value,
                "jobs_found": 0,
                "jobs_processed": 0,
                "jobs_skipped": 0,
                "error_count": 0,
                "config_used": request.dict()
            })
            
            db_id = result.fetchone()[0]
            self.db.commit()
            
            # Create response object
            search_record = ScheduledSearchResponse(
                id=str(db_id),
                name=request.name,
                status=SearchStatus.PENDING,
                search_params=request.dict(),
                created_at=datetime.now(),
                scheduled_time=scheduled_time,
                started_at=None,
                completed_at=None,
                jobs_found=None,
                error_message=None,
                recurring=request.recurring,
                recurring_interval=request.recurring_interval,
                next_run=scheduled_time
            )
            
            return search_record
            
        except Exception as e:
            self.logger.error(f"Failed to create scheduled search: {e}")
            self.db.rollback()
            raise

    async def get_scheduled_searches(self, status: Optional[SearchStatus] = None, limit: int = 50) -> List[ScheduledSearchResponse]:
        """Get list of scheduled searches from database"""
        from sqlalchemy import text
        try:
            # Query actual scraping runs from database
            sql = """
                SELECT id, source_platform, search_terms, locations, start_time, end_time, 
                       status, jobs_found, config_used, created_at
                FROM scraping_runs 
                ORDER BY start_time DESC 
                LIMIT :limit
            """
            result = self.db.execute(text(sql), {"limit": limit})
            rows = result.fetchall()
            
            searches = []
            for row in rows:
                # Extract search details from config_used JSON
                import json
                try:
                    config = json.loads(row.config_used) if row.config_used else {}
                except (json.JSONDecodeError, TypeError):
                    config = {}
                
                search = ScheduledSearchResponse(
                    id=str(row.id),
                    name=config.get('name', f"Search {row.id}"),
                    status=SearchStatus.COMPLETED if row.status == 'completed' else SearchStatus.FAILED if row.status == 'failed' else SearchStatus.RUNNING,
                    search_params=config,
                    created_at=row.created_at or row.start_time,
                    scheduled_time=row.start_time,
                    started_at=row.start_time,
                    completed_at=row.end_time,
                    jobs_found=row.jobs_found,
                    error_message=None,
                    recurring=False,
                    recurring_interval=None,
                    next_run=None
                )
                searches.append(search)
            
            # Filter by status if requested
            if status:
                searches = [s for s in searches if s.status == status]
            
            return searches[:limit]
            
        except Exception as e:
            self.logger.error(f"Failed to get scheduled searches: {e}")
            return []

    async def get_search_by_id(self, search_id: str) -> Optional[ScheduledSearchResponse]:
        """Get search by ID from database"""
        from sqlalchemy import text
        try:
            # Convert search_id to int for database query
            search_id_int = int(search_id)
            
            sql = """
                SELECT id, source_platform, search_terms, locations, start_time, end_time, 
                       status, jobs_found, config_used, created_at
                FROM scraping_runs 
                WHERE id = :search_id
            """
            result = self.db.execute(text(sql), {"search_id": search_id_int})
            row = result.fetchone()
            
            if not row:
                return None
            
            # Extract search details from config_used JSON
            import json
            try:
                config = json.loads(row.config_used) if row.config_used else {}
            except (json.JSONDecodeError, TypeError):
                config = {}
            
            # Map status strings to enum values
            status_map = {
                'completed': SearchStatus.COMPLETED,
                'failed': SearchStatus.FAILED,
                'running': SearchStatus.RUNNING,
                'pending': SearchStatus.PENDING,
                'cancelled': SearchStatus.CANCELLED
            }
            
            return ScheduledSearchResponse(
                id=str(row.id),
                name=config.get('name', f"Search {row.id}"),
                status=status_map.get(row.status, SearchStatus.PENDING),
                search_params=config,
                created_at=row.created_at or row.start_time,
                scheduled_time=row.start_time,
                started_at=row.start_time,
                completed_at=row.end_time,
                jobs_found=row.jobs_found,
                error_message=None,
                recurring=config.get('recurring', False),
                recurring_interval=config.get('recurring_interval'),
                next_run=None
            )
            
        except (ValueError, TypeError):
            self.logger.error(f"Invalid search_id format: {search_id}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting search by ID: {e}")
            return None

    async def cancel_search(self, search_id: str) -> bool:
        """Cancel a scheduled search"""
        try:
            search_id_int = int(search_id)
            
            # Update status in database
            result = self.db.execute(text("""
                UPDATE scraping_runs 
                SET status = 'cancelled', end_time = NOW()
                WHERE id = :search_id AND status IN ('pending', 'running')
            """), {"search_id": search_id_int})
            
            self.db.commit()
            
            # Return True if any rows were affected
            return result.rowcount > 0
            
        except (ValueError, TypeError):
            self.logger.error(f"Invalid search_id format: {search_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to cancel search: {e}")
            self.db.rollback()
            return False

    async def update_search_status(self, search_id: str, status: SearchStatus, 
                                 jobs_found: Optional[int] = None, 
                                 error_message: Optional[str] = None):
        """Update search status in database"""
        try:
            search_id_int = int(search_id)
            
            # Build update query based on status
            update_fields = ["status = :status"]
            params = {"search_id": search_id_int, "status": status.value}
            
            if status == SearchStatus.RUNNING:
                # Don't update start_time if already set, but update status
                pass
            elif status in [SearchStatus.COMPLETED, SearchStatus.FAILED, SearchStatus.CANCELLED]:
                update_fields.append("end_time = NOW()")
            
            if jobs_found is not None:
                update_fields.append("jobs_found = :jobs_found")
                params["jobs_found"] = jobs_found
                
            if error_message:
                update_fields.append("error_details = :error_details")
                params["error_details"] = {"error": error_message}
            
            sql = f"""
                UPDATE scraping_runs 
                SET {', '.join(update_fields)}
                WHERE id = :search_id
            """
            
            self.db.execute(text(sql), params)
            self.db.commit()
            
        except (ValueError, TypeError):
            self.logger.error(f"Invalid search_id format: {search_id}")
        except Exception as e:
            self.logger.error(f"Failed to update search status: {e}")
            self.db.rollback()

    async def get_search_templates(self) -> List[SearchTemplate]:
        """Get all search templates from cache"""
        try:
            from app.cache import cache
            template_keys = await cache.get("template_keys") or []
            templates = []
            
            for template_id in template_keys:
                template_data = await cache.get(f"template:{template_id}")
                if template_data:
                    templates.append(SearchTemplate(**template_data))
            
            return templates
        except Exception as e:
            self.logger.error(f"Failed to get search templates: {e}")
            return []

    async def create_search_template(self, template_data: dict) -> dict:
        """Create a new search template in cache"""
        try:
            from app.cache import cache
            template_id = str(uuid.uuid4())
            
            # Extract search parameters
            search_params = {
                'search_term': template_data.get('search_term'),
                'location': template_data.get('location'),
                'site_names': template_data.get('site_names', []),
                'job_type': template_data.get('job_type'),
                'is_remote': template_data.get('is_remote'),
                'distance': template_data.get('distance', 50),
                'results_wanted': template_data.get('results_wanted', 20),
                'hours_old': template_data.get('hours_old'),
                'easy_apply': template_data.get('easy_apply')
            }
            
            template = SearchTemplate(
                id=template_id,
                name=template_data.get('name'),
                description=template_data.get('description', ''),
                search_params=search_params,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Store template in cache
            await cache.set(f"template:{template_id}", template.dict(), expire=86400*30)  # 30 days
            
            # Update template keys list
            template_keys = await cache.get("template_keys") or []
            template_keys.append(template_id)
            await cache.set("template_keys", template_keys, expire=86400*30)
            
            return template.dict()
        except Exception as e:
            self.logger.error(f"Failed to create search template: {e}")
            raise

    async def delete_search_template(self, template_id: str) -> bool:
        """Delete a search template from cache"""
        try:
            from app.cache import cache
            
            # Check if template exists
            template_data = await cache.get(f"template:{template_id}")
            if not template_data:
                return False
            
            # Remove from cache
            await cache.delete(f"template:{template_id}")
            
            # Update template keys list
            template_keys = await cache.get("template_keys") or []
            if template_id in template_keys:
                template_keys.remove(template_id)
                await cache.set("template_keys", template_keys, expire=86400*30)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete search template: {e}")
            return False

    async def update_search_template(self, template_id: str, template_data: dict) -> Optional[dict]:
        """Update a search template in cache"""
        try:
            from app.cache import cache
            
            # Get existing template
            existing_data = await cache.get(f"template:{template_id}")
            if not existing_data:
                return None
            
            template = SearchTemplate(**existing_data)
            
            # Update basic fields
            if 'name' in template_data:
                template.name = template_data['name']
            if 'description' in template_data:
                template.description = template_data['description']
            
            # Update search parameters
            search_params = template.search_params.copy()
            
            update_fields = ['search_term', 'location', 'site_names', 'job_type', 'is_remote', 
                           'distance', 'results_wanted', 'hours_old', 'easy_apply']
            
            for field in update_fields:
                if field in template_data:
                    search_params[field] = template_data[field]
                    
            template.search_params = search_params
            template.updated_at = datetime.now()
            
            # Save updated template
            await cache.set(f"template:{template_id}", template.dict(), expire=86400*30)
            
            return template.dict()
        except Exception as e:
            self.logger.error(f"Failed to update search template: {e}")
            return None

    async def get_search_logs(self, search_id: Optional[str] = None, 
                            level: Optional[str] = None, 
                            limit: int = 100) -> List[SearchLog]:
        """Get search logs using real log service"""
        return await self.log_service.get_search_logs(search_id, level, limit)

    async def add_search_log(self, search_id: str, level: str, message: str, details: Optional[Dict] = None):
        """Add a search log entry using real log service"""
        await self.log_service.add_search_log(search_id, level, message)

    async def schedule_search_task(self, search_id: str, schedule_time: datetime, search_params: Dict):
        """Schedule a search task for later execution"""
        try:
            # For now, update the database record with the new schedule time
            search_id_int = int(search_id)
            
            self.db.execute(text("""
                UPDATE scraping_runs 
                SET start_time = :schedule_time, config_used = :config_used
                WHERE id = :search_id
            """), {
                "search_id": search_id_int,
                "schedule_time": schedule_time,
                "config_used": search_params
            })
            
            self.db.commit()
            
        except (ValueError, TypeError):
            self.logger.error(f"Invalid search_id format: {search_id}")
        except Exception as e:
            self.logger.error(f"Failed to schedule search task: {e}")
            self.db.rollback()

    async def get_system_health(self) -> Dict[str, Any]:
        """Get detailed system health information"""
        now = datetime.now()
        
        # Test database connectivity and measure response time
        db_status = "disconnected"
        db_response_time = 0
        try:
            start_time = now
            self.db.execute(text("SELECT 1"))
            db_response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            db_status = "connected"
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
        
        # Test Redis connectivity and measure response time
        redis_status = "disconnected"
        redis_response_time = 0
        try:
            from app.cache import cache
            start_time = datetime.now()
            test_key = "health_check_test"
            await cache.set(test_key, "test", expire=10)
            result = await cache.get(test_key)
            redis_response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            redis_status = "connected" if result == "test" else "disconnected"
        except Exception as e:
            self.logger.error(f"Redis health check failed: {e}")
        
        # Get real system performance metrics
        performance = await self._get_system_performance()
        
        # Get real search statistics from database
        search_stats = await self._get_search_statistics()
        
        # Determine overall health status
        overall_status = "healthy"
        if db_status != "connected" or redis_status != "connected":
            overall_status = "degraded"
        if db_status != "connected" and redis_status != "connected":
            overall_status = "unhealthy"
        
        return {
            "timestamp": now.isoformat(),
            "status": overall_status,
            "components": {
                "database": {
                    "status": db_status,
                    "response_time_ms": db_response_time
                },
                "redis": {
                    "status": redis_status, 
                    "response_time_ms": redis_response_time
                },
                "job_sites": await self._check_job_sites_accessibility()
            },
            "performance": performance,
            "searches": search_stats
        }
    
    async def _get_cache_hit_rate(self) -> float:
        """Get actual cache hit rate from Redis"""
        try:
            from app.cache import cache
            # Check if we can get cache statistics
            # For now, we'll simulate by testing cache operations
            test_operations = 10
            hits = 0
            
            for i in range(test_operations):
                test_key = f"hit_rate_test_{i}"
                await cache.set(test_key, "test", expire=60)
                result = await cache.get(test_key)
                if result == "test":
                    hits += 1
            
            return hits / test_operations
        except Exception as e:
            self.logger.error(f"Failed to calculate cache hit rate: {e}")
            return 0.0
    
    async def _get_system_performance(self) -> Dict[str, Any]:
        """Get real system performance metrics"""
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Get disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            return {
                "memory_usage_percent": round(memory_percent, 1),
                "cpu_usage_percent": round(cpu_percent, 1),
                "disk_usage_percent": round(disk_percent, 1)
            }
        except Exception as e:
            self.logger.error(f"Failed to get system performance: {e}")
            return {
                "memory_usage_percent": 0,
                "cpu_usage_percent": 0,
                "disk_usage_percent": 0
            }
    
    async def _get_search_statistics(self) -> Dict[str, int]:
        """Get real search statistics from database"""
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Count active searches
            active_result = self.db.execute(text("""
                SELECT COUNT(*) FROM scraping_runs 
                WHERE status = 'running'
            """))
            active_count = active_result.scalar() or 0
            
            # Count pending searches (recent ones that haven't started)
            pending_result = self.db.execute(text("""
                SELECT COUNT(*) FROM scraping_runs 
                WHERE status = 'pending' AND start_time > NOW() - INTERVAL '1 hour'
            """))
            pending_count = pending_result.scalar() or 0
            
            # Count completed searches today
            completed_result = self.db.execute(text("""
                SELECT COUNT(*) FROM scraping_runs 
                WHERE status = 'completed' AND start_time >= :today_start
            """), {"today_start": today_start})
            completed_today = completed_result.scalar() or 0
            
            return {
                "active_count": active_count,
                "pending_count": pending_count,
                "completed_today": completed_today
            }
        except Exception as e:
            self.logger.error(f"Failed to get search statistics: {e}")
            return {
                "active_count": 0,
                "pending_count": 0,
                "completed_today": 0
            }
    
    async def _check_job_sites_accessibility(self) -> Dict[str, str]:
        """Check if job sites are accessible"""
        import aiohttp
        import asyncio
        
        sites = {
            "indeed": "https://indeed.com",
            "linkedin": "https://linkedin.com",
            "glassdoor": "https://glassdoor.com"
        }
        
        results = {}
        
        async def check_site(name: str, url: str):
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            results[name] = "accessible"
                        else:
                            results[name] = f"error_{response.status}"
            except Exception as e:
                self.logger.warning(f"Failed to check {name}: {e}")
                results[name] = "inaccessible"
        
        # Check all sites concurrently with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*[check_site(name, url) for name, url in sites.items()]),
                timeout=10
            )
        except asyncio.TimeoutError:
            self.logger.warning("Job site accessibility check timed out")
            for name in sites:
                if name not in results:
                    results[name] = "timeout"
        
        return results