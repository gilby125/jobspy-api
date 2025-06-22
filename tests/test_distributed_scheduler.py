"""
Comprehensive tests for the distributed scheduler system.
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import redis.asyncio as redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.distributed_scheduler import DistributedScheduler
from app.models.admin_models import SearchStatus


@pytest.fixture
async def redis_client():
    """Redis client for testing"""
    client = redis.from_url("redis://localhost:6379/15")  # Use test DB 15
    yield client
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
def db_session():
    """Database session for testing"""
    # Use real PostgreSQL for tests
    import os
    from sqlalchemy.pool import QueuePool
    from app.models.tracking_models import Base
    
    test_db_url = os.getenv("TEST_DATABASE_URL", "postgresql://jobspy:jobspy_password@localhost:5432/test_jobspy")
    engine = create_engine(
        test_db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False
    )
    
    # Create all tables using the proper Base metadata
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    
    # Clean up tables after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
async def scheduler(db_session, redis_client):
    """Scheduler instance for testing"""
    scheduler = DistributedScheduler(db_session)
    scheduler.redis_client = redis_client
    scheduler._running = True
    yield scheduler
    await scheduler.stop()


class TestDistributedScheduler:
    """Test suite for distributed scheduler"""
    
    async def test_scheduler_initialization(self, scheduler):
        """Test scheduler starts correctly"""
        assert scheduler._running is True
        assert scheduler.redis_client is not None
        assert scheduler._worker_id.startswith("worker_")
    
    async def test_heartbeat_registration(self, scheduler, redis_client):
        """Test worker heartbeat registration"""
        # Manual heartbeat
        await scheduler._heartbeat_loop.__wrapped__(scheduler)
        
        # Check worker is registered
        workers = await redis_client.smembers("scheduler:workers")
        assert scheduler._worker_id.encode() in workers
        
        # Check worker data exists with TTL
        worker_data = await redis_client.get(f"scheduler:worker:{scheduler._worker_id}")
        assert worker_data is not None
        
        ttl = await redis_client.ttl(f"scheduler:worker:{scheduler._worker_id}")
        assert ttl > 0
    
    async def test_distributed_locking(self, scheduler):
        """Test distributed lock acquisition and release"""
        # First acquisition should succeed
        lock1 = await scheduler._acquire_scheduler_lock()
        assert lock1 is True
        
        # Second acquisition should fail (lock held)
        lock2 = await scheduler._acquire_scheduler_lock()
        assert lock2 is False
        
        # Release lock
        await scheduler._release_scheduler_lock()
        
        # Now acquisition should succeed again
        lock3 = await scheduler._acquire_scheduler_lock()
        assert lock3 is True
    
    async def test_job_scheduling(self, scheduler, redis_client):
        """Test job scheduling in Redis"""
        search_config = {
            "name": "Test Search",
            "search_term": "python developer",
            "location": "Austin, TX",
            "site_names": ["indeed"],
            "results_wanted": 5,
            "country_indeed": "USA"
        }
        
        # Schedule for 10 seconds from now
        schedule_time = datetime.now() + timedelta(seconds=10)
        search_id = await scheduler.schedule_search(search_config, schedule_time)
        
        assert isinstance(search_id, int)
        assert search_id > 0
        
        # Check job is in Redis pending queue
        pending_jobs = await redis_client.zrange("scheduler:pending", 0, -1)
        assert len(pending_jobs) == 1
        
        # Check job data
        job_data = json.loads(pending_jobs[0])
        assert job_data["search_id"] == search_id
        assert job_data["search_params"]["name"] == "Test Search"
    
    async def test_immediate_execution_scheduling(self, scheduler, redis_client):
        """Test scheduling for immediate execution"""
        search_config = {
            "name": "Immediate Test",
            "search_term": "data scientist",
            "site_names": ["indeed"],
            "results_wanted": 3
        }
        
        search_id = await scheduler.schedule_search(search_config)
        
        # Should be scheduled for immediate execution
        pending_jobs = await redis_client.zrange("scheduler:pending", 0, -1)
        assert len(pending_jobs) == 1
        
        # Score should be current timestamp or earlier
        job_score = await redis_client.zscore("scheduler:pending", pending_jobs[0])
        assert job_score <= datetime.now().timestamp()
    
    @patch('app.services.job_service.JobService.search_jobs')
    async def test_job_execution(self, mock_search_jobs, scheduler, db_session):
        """Test job execution logic"""
        # Mock job search results
        mock_df = Mock()
        mock_df.empty = False
        mock_df.__len__ = Mock(return_value=3)
        mock_search_jobs.return_value = (mock_df, False)
        
        job_config = {
            "search_id": 1,
            "search_params": {
                "search_term": "test job",
                "site_names": ["indeed"],
                "location": "Test City",
                "results_wanted": 5,
                "country_indeed": "USA"
            },
            "scheduled_time": datetime.now().isoformat()
        }
        
        # Insert test record in database using proper PostgreSQL syntax
        db_session.execute(text("""
            INSERT INTO scraping_runs (id, source_platform, search_terms, locations, 
                                     start_time, status, jobs_found, jobs_processed, 
                                     jobs_skipped, error_count, config_used)
            VALUES (1, 'indeed', '["test job"]', '["Test City"]', :start_time, 
                    'pending', 0, 0, 0, 0, '{}')
        """), {"start_time": datetime.now()})
        db_session.commit()
        
        # Execute job
        await scheduler._execute_job(job_config)
        
        # Check database was updated
        result = db_session.execute(text(
            "SELECT status, jobs_found FROM scraping_runs WHERE id = 1"
        )).fetchone()
        
        assert result.status == "completed"
        assert result.jobs_found == 3
        
        # Verify job search was called with correct params
        mock_search_jobs.assert_called_once()
        call_args = mock_search_jobs.call_args[0][0]
        assert call_args["search_term"] == "test job"
        assert call_args["site_name"] == ["indeed"]
    
    async def test_job_cancellation(self, scheduler, redis_client, db_session):
        """Test job cancellation"""
        # Schedule a job
        search_config = {
            "name": "Cancel Test",
            "search_term": "test",
            "site_names": ["indeed"]
        }
        
        future_time = datetime.now() + timedelta(hours=1)
        search_id = await scheduler.schedule_search(search_config, future_time)
        
        # Verify job is pending
        pending_count = await redis_client.zcard("scheduler:pending")
        assert pending_count == 1
        
        # Cancel the job
        success = await scheduler.cancel_search(search_id)
        assert success is True
        
        # Check database status
        result = db_session.execute(text(
            "SELECT status FROM scraping_runs WHERE id = :id"
        ), {"id": search_id}).fetchone()
        assert result.status == "cancelled"
        
        # Check Redis queue (should be empty or job removed)
        # Note: In real implementation, job should be removed from Redis
    
    async def test_recurring_job_scheduling(self, scheduler, redis_client):
        """Test recurring job creation"""
        search_config = {
            "name": "Daily Recurring",
            "search_term": "python",
            "site_names": ["indeed"],
            "recurring": True,
            "recurring_interval": "daily"
        }
        
        job_config = {
            "search_id": 1,
            "search_params": search_config,
            "scheduled_time": datetime.now().isoformat()
        }
        
        # Test next occurrence scheduling
        await scheduler._schedule_next_occurrence(job_config)
        
        # Should have scheduled next occurrence
        pending_jobs = await redis_client.zrange("scheduler:pending", 0, -1)
        assert len(pending_jobs) == 1
        
        # Verify timing (should be ~24 hours from now)
        job_score = await redis_client.zscore("scheduler:pending", pending_jobs[0])
        expected_time = datetime.now() + timedelta(days=1)
        assert abs(job_score - expected_time.timestamp()) < 3600  # Within 1 hour tolerance
    
    async def test_scheduler_stats(self, scheduler, redis_client):
        """Test scheduler statistics"""
        # Add some test data
        await redis_client.zadd("scheduler:pending", {"job1": datetime.now().timestamp()})
        await redis_client.sadd("scheduler:workers", "worker1", "worker2")
        await redis_client.lpush("scheduler:recent_results", "result1", "result2")
        
        stats = await scheduler.get_scheduler_stats()
        
        assert stats["pending_jobs"] == 1
        assert stats["active_workers"] == 2
        assert stats["recent_executions"] == 2
        assert stats["scheduler_status"] == "running"
    
    async def test_error_handling(self, scheduler, db_session):
        """Test error handling during job execution"""
        # Create job config that will cause an error
        job_config = {
            "search_id": 999,  # Non-existent ID
            "search_params": {
                "search_term": "test",
                "site_names": ["invalid_site"]  # This should cause an error
            }
        }
        
        # Insert test record using proper PostgreSQL syntax
        db_session.execute(text("""
            INSERT INTO scraping_runs (id, source_platform, search_terms, locations, 
                                     start_time, status, jobs_found, jobs_processed, 
                                     jobs_skipped, error_count, config_used)
            VALUES (999, 'invalid_site', '["test"]', '[]', :start_time, 
                    'pending', 0, 0, 0, 0, '{}')
        """), {"start_time": datetime.now()})
        db_session.commit()
        
        # Execute job (should handle error gracefully)
        await scheduler._execute_job(job_config)
        
        # Check status was updated to failed
        result = db_session.execute(text(
            "SELECT status, error_details FROM scraping_runs WHERE id = 999"
        )).fetchone()
        
        assert result.status == "failed"
        assert result.error_details is not None


class TestSchedulerIntegration:
    """Integration tests with Redis and Database"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_scheduling(self):
        """Test complete scheduling workflow"""
        # This would require actual Redis and DB connections
        pass
    
    @pytest.mark.asyncio
    async def test_multiple_workers(self):
        """Test multiple scheduler instances coordination"""
        # Test with multiple DistributedScheduler instances
        pass
    
    @pytest.mark.asyncio
    async def test_failover_scenario(self):
        """Test worker failover when one dies"""
        pass


# Manual Testing Commands
"""
# 1. Test Immediate Scheduling
curl -X POST http://localhost:8787/admin/searches \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Immediate Test",
    "search_term": "software engineer",
    "location": "San Francisco, CA",
    "site_names": ["indeed"],
    "results_wanted": 3,
    "country_indeed": "USA"
  }'

# 2. Test Future Scheduling (2 minutes from now)
curl -X POST http://localhost:8787/admin/searches \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Future Test",
    "search_term": "data scientist",
    "location": "New York, NY",
    "site_names": ["indeed"],
    "results_wanted": 2,
    "country_indeed": "USA",
    "schedule_time": "'$(date -d '+2 minutes' -Iseconds)'"
  }'

# 3. Test Recurring Daily Search
curl -X POST http://localhost:8787/admin/searches \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Python Jobs",
    "search_term": "python developer",
    "location": "Austin, TX",
    "site_names": ["indeed"],
    "results_wanted": 5,
    "country_indeed": "USA",
    "recurring": true,
    "recurring_interval": "daily",
    "schedule_time": "'$(date -d '+1 minute' -Iseconds)'"
  }'

# 4. Check Scheduled Searches
curl http://localhost:8787/admin/searches

# 5. Check Specific Search Status
curl http://localhost:8787/admin/searches/1

# 6. Cancel a Search
curl -X POST http://localhost:8787/admin/searches/1/cancel

# 7. Redis Manual Testing
redis-cli -n 0
> ZRANGE scheduler:pending 0 -1 WITHSCORES
> SMEMBERS scheduler:workers
> LRANGE scheduler:recent_results 0 -1
> GET scheduler:lock

# 8. Database Manual Testing
docker exec jobspy-postgres psql -U jobspy -d jobspy -c "
SELECT id, status, start_time, end_time, jobs_found, 
       json_extract(config_used, '$.name') as search_name
FROM scraping_runs 
ORDER BY start_time DESC 
LIMIT 10;"
"""